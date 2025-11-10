from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, g
from pymongo.errors import DuplicateKeyError

from .limiter import limiter, rate_limit_key_for_request
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
import jwt
from bson import ObjectId

auth = Blueprint("auth", __name__)


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
        return jsonify({"error": "invalid credentials"}), 401

    if not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401

    access_token = generate_access_jwt(str(user["_id"]))
    refresh_token = generate_refresh_jwt(str(user["_id"]))
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

        resp = jsonify({"access_token": new_access_token})
        set_refresh_cookie(resp, new_refresh_token)
        set_access_cookie(resp, new_access_token)
        return resp, 200

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "invalid or expired refresh token"}), 401
    except Exception:
        return jsonify({"error": "refresh token verification failed"}), 401


@auth.route("/auth/logout", methods=["POST"])
@limiter.limit("60/hour")
def logout():
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
        return jsonify({"error": "email already registered"}), 409
    except Exception:
        return jsonify({"error": "failed to create user"}), 500

    # Issue tokens just like login
    access_token = generate_access_jwt(str(user_id))
    refresh_token = generate_refresh_jwt(str(user_id))
    resp = jsonify(
        {
            "access_token": access_token,
            "user": get_user_profile({"_id": user_id, **user_doc}),
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
            return jsonify({"success": True, "message": "password set successfully"})
        else:
            return jsonify({"error": "failed to set password"}), 500

    except Exception as e:
        print(f"Error setting password: {e}")
        return jsonify({"error": "failed to set password"}), 500


@auth.route("/login", methods=["GET"])
def login_redirect():
    """Redirect /login to home page to prevent shortened URL conflicts"""
    from flask import redirect

    return redirect("/", code=302)


@auth.route("/register", methods=["GET"])
@auth.route("/signup", methods=["GET"])
def register_redirect():
    """Redirect /register and /signup to home page to prevent shortened URL conflicts"""
    from flask import redirect

    return redirect("/", code=302)
