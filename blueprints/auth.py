from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, g, redirect, render_template
from pymongo.errors import DuplicateKeyError

from .limiter import limiter, rate_limit_key_for_request
from utils.logger import get_logger
from utils.auth_utils import (
    verify_password,
    hash_password,
    generate_access_jwt,
    generate_refresh_jwt,
    verify_refresh_jwt,
    set_refresh_cookie,
    set_access_cookie,
    clear_refresh_cookie,
    clear_access_cookie,
    requires_auth,
)
from utils.password_utils import validate_password
from utils.mongo_utils import (
    get_user_by_email,
    get_user_by_id,
    users_collection,
)
from utils.url_utils import get_client_ip
from utils.auth_utils import get_user_profile
from utils.verification_utils import (
    create_email_verification_otp,
    create_password_reset_otp,
    verify_otp,
    is_rate_limited,
    TOKEN_TYPE_EMAIL_VERIFY,
    TOKEN_TYPE_PASSWORD_RESET,
)
from utils.email_service import email_service
import jwt
from bson import ObjectId

auth = Blueprint("auth", __name__)
log = get_logger(__name__)


@auth.route("/auth/login", methods=["POST"])
@limiter.limit("5/minute")
@limiter.limit("50/day")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    user = get_user_by_email(email)
    if not user or not user.get("password_hash"):
        # Do not reveal which part failed
        log.warning(
            "login_failed", reason="invalid_credentials", email_exists=bool(user)
        )
        return jsonify({"error": "invalid credentials"}), 401

    if not verify_password(password, user["password_hash"]):
        log.warning("login_failed", reason="invalid_password", user_id=str(user["_id"]))
        return jsonify({"error": "invalid credentials"}), 401

    email_verified = user.get("email_verified", False)
    access_token = generate_access_jwt(str(user["_id"]), email_verified)
    refresh_token = generate_refresh_jwt(str(user["_id"]), email_verified)

    log.info("login_success", user_id=str(user["_id"]), auth_method="password")

    resp = jsonify({"access_token": access_token, "user": get_user_profile(user)})
    set_refresh_cookie(resp, refresh_token)
    set_access_cookie(resp, access_token)
    return resp, 200


@auth.route("/auth/refresh", methods=["POST"])
@limiter.limit("20/minute")
def refresh():
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return jsonify({"error": "missing refresh token"}), 401

    try:
        # Verify refresh token (stateless)
        refresh_claims = verify_refresh_jwt(refresh_token)
        user_id = refresh_claims.get("sub")

        # Generate new tokens (token rotation for security)
        new_access_token = generate_access_jwt(user_id)
        new_refresh_token = generate_refresh_jwt(user_id)

        log.info("token_refreshed", user_id=user_id)

        resp = jsonify({"access_token": new_access_token})
        set_refresh_cookie(resp, new_refresh_token)
        set_access_cookie(resp, new_access_token)
        return resp, 200

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        log.warning("token_refresh_failed", reason="expired_or_invalid", error=str(e))
        return jsonify({"error": "invalid or expired refresh token"}), 401
    except Exception as e:
        log.error("token_refresh_error", error=str(e), error_type=type(e).__name__)
        return jsonify({"error": "refresh token verification failed"}), 401


@auth.route("/auth/logout", methods=["POST"])
@limiter.limit("60/hour")
def logout():
    user_id = getattr(g, "user_id", None)
    if user_id:
        log.info("logout", user_id=str(user_id))

    resp = jsonify({"success": True})
    clear_refresh_cookie(resp)
    clear_access_cookie(resp)
    return resp, 200


@auth.route("/auth/me", methods=["GET"])
@requires_auth
@limiter.limit("60/minute", key_func=rate_limit_key_for_request)
def me():
    user_id = g.user_id
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify({"user": get_user_profile(user)})


@auth.route("/auth/register", methods=["POST"])
@limiter.limit("5/minute")
@limiter.limit("50/day")
def register():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    user_name = (body.get("user_name") or "").strip() or None
    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    # Validate password with comprehensive checks
    is_valid, missing_requirements = validate_password(password)
    if not is_valid:
        return jsonify(
            {
                "error": "Password does not meet requirements",
                "missing_requirements": missing_requirements,
            }
        ), 400

    # Check existing user
    existing = get_user_by_email(email)
    if existing:
        log.warning("registration_failed", reason="email_exists")
        return jsonify({"error": "email already registered"}), 409

    password_hash = hash_password(password)
    user_doc = {
        "email": email,
        "email_verified": False,  # Email not verified initially
        "password_hash": password_hash,
        "password_set": True,
        "user_name": user_name,
        "pfp": None,
        "auth_providers": [],
        "plan": "free",
        "signup_ip": get_client_ip(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "status": "ACTIVE",
    }
    try:
        insert_result = users_collection.insert_one(user_doc)
        user_id = insert_result.inserted_id
    except DuplicateKeyError:
        # Race condition: email was registered between our check and insert
        log.warning("registration_failed", reason="race_condition_duplicate")
        return jsonify({"error": "email already registered"}), 409
    except Exception as e:
        log.error("registration_failed", reason="database_error", error=str(e))
        return jsonify({"error": "failed to create user"}), 500

    # Issue tokens for authentication (but user still needs to verify email)
    access_token = generate_access_jwt(str(user_id), email_verified=False)
    refresh_token = generate_refresh_jwt(str(user_id), email_verified=False)

    log.info(
        "user_registered",
        user_id=str(user_id),
        auth_method="password",
        has_username=bool(user_name),
    )

    # Send verification email automatically
    verification_sent = False
    try:
        success, otp_code, error = create_email_verification_otp(str(user_id), email)
        if success and otp_code:
            email_service.send_verification_email(email, user_name, otp_code)
            verification_sent = True
            log.info("registration_verification_email_sent", user_id=str(user_id))
    except Exception as e:
        # Don't fail registration if email sending fails
        log.error(
            "registration_verification_email_failed",
            user_id=str(user_id),
            error=str(e),
        )

    resp = jsonify(
        {
            "access_token": access_token,
            "user": get_user_profile({"_id": user_id, **user_doc}),
            "requires_verification": True,
            "verification_sent": verification_sent,
        }
    )
    set_refresh_cookie(resp, refresh_token)
    set_access_cookie(resp, access_token)
    return resp, 201


@auth.route("/auth/set-password", methods=["POST"])
@requires_auth
@limiter.limit("5/minute")
def set_password():
    """Set password for OAuth-only users"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    if user.get("password_set", False):
        return jsonify({"error": "password already set"}), 400

    body = request.get_json(silent=True) or {}
    password = body.get("password") or ""

    if not password:
        return jsonify({"error": "password is required"}), 400

    # Validate password with comprehensive checks
    is_valid, missing_requirements = validate_password(password)
    if not is_valid:
        return jsonify(
            {
                "error": "Password does not meet requirements",
                "missing_requirements": missing_requirements,
            }
        ), 400

    try:
        password_hash = hash_password(password)

        result = users_collection.update_one(
            {"_id": ObjectId(g.user_id)},
            {
                "$set": {
                    "password_hash": password_hash,
                    "password_set": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.modified_count > 0:
            log.info("password_set", user_id=g.user_id)
            return jsonify({"success": True, "message": "password set successfully"})
        else:
            log.error("password_set_failed", user_id=g.user_id, reason="no_update")
            return jsonify({"error": "failed to set password"}), 500

    except Exception as e:
        log.error(
            "password_set_failed",
            user_id=g.user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return jsonify({"error": "failed to set password"}), 500


@auth.route("/login", methods=["GET"])
def login_redirect():
    """Redirect /login to home page to prevent shortened URL conflicts"""
    return redirect("/", code=302)


@auth.route("/register", methods=["GET"])
@auth.route("/signup", methods=["GET"])
def register_redirect():
    """Redirect /register and /signup to home page to prevent shortened URL conflicts"""
    return redirect("/", code=302)


@auth.route("/auth/verify", methods=["GET"])
@requires_auth
@limiter.limit("60/minute", key_func=rate_limit_key_for_request)
def verify_page():
    """Email verification page"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    # Redirect to dashboard if already verified
    if user.get("email_verified", False):
        return redirect("/dashboard")

    return render_template("verify.html", email=user.get("email"))


@auth.route("/auth/send-verification", methods=["POST"])
@requires_auth
@limiter.limit("3/hour", key_func=rate_limit_key_for_request)
def send_verification_email():
    """Send email verification OTP to authenticated user"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    if user.get("email_verified", False):
        return jsonify({"error": "email already verified"}), 400

    # Check rate limiting
    if is_rate_limited(g.user_id, TOKEN_TYPE_EMAIL_VERIFY):
        log.warning("verification_rate_limited", user_id=g.user_id)
        return (
            jsonify(
                {
                    "error": "too many requests",
                    "message": "Please wait before requesting another verification email",
                }
            ),
            429,
        )

    # Create OTP
    success, otp_code, error = create_email_verification_otp(g.user_id, user["email"])

    if not success:
        return jsonify({"error": error or "failed to create verification code"}), 500

    # Send email
    email_sent = email_service.send_verification_email(
        user["email"], user.get("user_name"), otp_code
    )

    if not email_sent:
        log.error("verification_email_send_failed", user_id=g.user_id)
        return jsonify({"error": "failed to send verification email"}), 500

    log.info("verification_email_sent", user_id=g.user_id, email=user["email"])

    return jsonify(
        {
            "success": True,
            "message": "verification code sent to your email",
            "expires_in": 600,
        }
    )


@auth.route("/auth/verify-email", methods=["POST"])
@requires_auth
@limiter.limit("10/hour", key_func=rate_limit_key_for_request)
def verify_email():
    """Verify email using OTP code"""
    user = get_user_by_id(g.user_id)
    if not user:
        return jsonify({"error": "user not found"}), 404

    if user.get("email_verified", False):
        return jsonify({"error": "email already verified"}), 400

    body = request.get_json(silent=True) or {}
    otp_code = (body.get("code") or "").strip()

    if not otp_code:
        return jsonify({"error": "verification code is required"}), 400

    # Verify OTP
    success, error = verify_otp(g.user_id, otp_code, TOKEN_TYPE_EMAIL_VERIFY)

    if not success:
        log.warning("email_verification_failed", user_id=g.user_id, error=error)
        return jsonify({"error": error or "invalid verification code"}), 400

    # Update user's email_verified status
    try:
        result = users_collection.update_one(
            {"_id": ObjectId(g.user_id)},
            {
                "$set": {
                    "email_verified": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.modified_count > 0:
            log.info("email_verified_success", user_id=g.user_id)

            # Issue new JWT tokens with email_verified=True
            new_access_token = generate_access_jwt(g.user_id, email_verified=True)
            new_refresh_token = generate_refresh_jwt(g.user_id, email_verified=True)

            # Send welcome email
            email_service.send_welcome_email(user["email"], user.get("user_name"))

            resp = jsonify(
                {
                    "success": True,
                    "message": "email verified successfully",
                    "email_verified": True,
                }
            )
            set_refresh_cookie(resp, new_refresh_token)
            set_access_cookie(resp, new_access_token)
            return resp
        else:
            log.error("email_verification_update_failed", user_id=g.user_id)
            return jsonify({"error": "failed to update verification status"}), 500

    except Exception as e:
        log.error(
            "email_verification_error",
            user_id=g.user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return jsonify({"error": "failed to verify email"}), 500


@auth.route("/auth/request-password-reset", methods=["POST"])
@limiter.limit("3/hour")
def request_password_reset():
    """Request password reset OTP"""
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()

    if not email:
        return jsonify({"error": "email is required"}), 400

    # Find user by email
    user = get_user_by_email(email)

    # Always return success to prevent email enumeration
    if not user:
        log.warning("password_reset_requested_nonexistent", email=email)
        return jsonify(
            {
                "success": True,
                "message": "if the email exists, a reset code has been sent",
            }
        )

    # Check if user has a password set
    if not user.get("password_set", False):
        log.warning("password_reset_no_password", user_id=str(user["_id"]))
        # Still return success for security
        return jsonify(
            {
                "success": True,
                "message": "if the email exists, a reset code has been sent",
            }
        )

    user_id = str(user["_id"])

    # Check rate limiting
    if is_rate_limited(user_id, TOKEN_TYPE_PASSWORD_RESET):
        log.warning("password_reset_rate_limited", user_id=user_id)
        # Don't reveal rate limiting for security
        return jsonify(
            {
                "success": True,
                "message": "if the email exists, a reset code has been sent",
            }
        )

    # Create OTP
    success, otp_code, error = create_password_reset_otp(user_id, email)

    if not success:
        log.error("password_reset_otp_creation_failed", user_id=user_id, error=error)
        # Still return success for security
        return jsonify(
            {
                "success": True,
                "message": "if the email exists, a reset code has been sent",
            }
        )

    # Send email
    email_sent = email_service.send_password_reset_email(
        email, user.get("user_name"), otp_code
    )

    if not email_sent:
        log.error("password_reset_email_send_failed", user_id=user_id)
        # Still return success for security
        return jsonify(
            {
                "success": True,
                "message": "if the email exists, a reset code has been sent",
            }
        )

    log.info("password_reset_email_sent", user_id=user_id)

    return jsonify(
        {
            "success": True,
            "message": "if the email exists, a reset code has been sent",
            "expires_in": 600,
        }
    )


@auth.route("/auth/reset-password", methods=["POST"])
@limiter.limit("5/hour")
def reset_password():
    """Reset password using OTP code"""
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    otp_code = (body.get("code") or "").strip()
    new_password = body.get("password") or ""

    if not email or not otp_code or not new_password:
        return (
            jsonify({"error": "email, code, and password are required"}),
            400,
        )

    # Find user
    user = get_user_by_email(email)
    if not user:
        return jsonify({"error": "invalid email or code"}), 400

    user_id = str(user["_id"])

    # Validate new password
    is_valid, missing_requirements = validate_password(new_password)
    if not is_valid:
        return jsonify(
            {
                "error": "password does not meet requirements",
                "missing_requirements": missing_requirements,
            }
        ), 400

    # Verify OTP
    success, error = verify_otp(user_id, otp_code, TOKEN_TYPE_PASSWORD_RESET)

    if not success:
        log.warning("password_reset_verification_failed", user_id=user_id, error=error)
        return jsonify({"error": error or "invalid or expired code"}), 400

    # Update password
    try:
        password_hash = hash_password(new_password)

        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "password_hash": password_hash,
                    "password_set": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.modified_count > 0:
            log.info("password_reset_success", user_id=user_id)
            return jsonify(
                {
                    "success": True,
                    "message": "password reset successfully",
                }
            )
        else:
            log.error("password_reset_update_failed", user_id=user_id)
            return jsonify({"error": "failed to reset password"}), 500

    except Exception as e:
        log.error(
            "password_reset_error",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return jsonify({"error": "failed to reset password"}), 500
