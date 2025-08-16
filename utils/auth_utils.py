import os
from datetime import datetime, timedelta, timezone
from functools import wraps, lru_cache

from flask import request, jsonify, g, make_response
import jwt
from argon2 import PasswordHasher


password_hasher = PasswordHasher()


@lru_cache(maxsize=1)
def _use_rs256() -> bool:
    return bool(os.getenv("JWT_PRIVATE_KEY") and os.getenv("JWT_PUBLIC_KEY"))


@lru_cache(maxsize=1)
def _jwt_keys():
    if _use_rs256():
        priv = os.getenv("JWT_PRIVATE_KEY") or ""
        pub = os.getenv("JWT_PUBLIC_KEY") or ""
        # Support keys provided via env with literal \n sequences
        priv = priv.replace("\\n", "\n").encode("utf-8")
        pub = pub.replace("\\n", "\n").encode("utf-8")
        return (priv, pub)
    else:
        secret = os.getenv("JWT_SECRET")
        if not secret:
            raise RuntimeError(
                "JWT_SECRET must be set when RS256 keys are not provided"
            )
        return (secret, secret)


@lru_cache(maxsize=1)
def _jwt_settings():
    issuer = os.getenv("JWT_ISSUER", "spoo.me")
    audience = os.getenv("JWT_AUDIENCE", "spoo.me.api")
    access_ttl = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))
    refresh_ttl = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", "2592000"))
    return issuer, audience, access_ttl, refresh_ttl


def hash_password(plain_password: str) -> str:
    return password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        password_hasher.verify(password_hash, plain_password)
        return True
    except Exception:
        return False


def generate_access_jwt(user_id: str) -> str:
    issuer, audience, access_ttl, _ = _jwt_settings()
    private_key, _ = _jwt_keys()
    algorithm = "RS256" if _use_rs256() else "HS256"
    now = datetime.now(timezone.utc)
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=access_ttl)).timestamp()),
    }
    return jwt.encode(claims, private_key, algorithm=algorithm)


def verify_access_jwt(token: str):
    issuer, audience, *_ = _jwt_settings()
    _, public_key = _jwt_keys()
    algorithm = "RS256" if _use_rs256() else "HS256"
    return jwt.decode(
        token, public_key, algorithms=[algorithm], audience=audience, issuer=issuer
    )


def generate_refresh_jwt(user_id: str) -> str:
    """Generate a stateless refresh JWT token."""
    issuer, audience, _, refresh_ttl = _jwt_settings()
    private_key, _ = _jwt_keys()
    algorithm = "RS256" if _use_rs256() else "HS256"
    now = datetime.now(timezone.utc)
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=refresh_ttl)).timestamp()),
        "type": "refresh",
    }
    return jwt.encode(claims, private_key, algorithm=algorithm)


def verify_refresh_jwt(token: str):
    """Verify and decode a refresh JWT token."""
    issuer, audience, *_ = _jwt_settings()
    _, public_key = _jwt_keys()
    algorithm = "RS256" if _use_rs256() else "HS256"
    claims = jwt.decode(
        token, public_key, algorithms=[algorithm], audience=audience, issuer=issuer
    )
    # Ensure it's a refresh token
    if claims.get("type") != "refresh":
        raise jwt.InvalidTokenError("Not a refresh token")
    return claims


def set_refresh_cookie(response, token: str):
    secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    *_, refresh_ttl = _jwt_settings()
    response.set_cookie(
        "refresh_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/",
        max_age=refresh_ttl,
    )
    return response


def clear_refresh_cookie(response):
    secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    response.set_cookie(
        "refresh_token",
        value="",
        expires=0,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/",
    )
    # Also clear any legacy cookie that was scoped to /auth/refresh
    response.set_cookie(
        "refresh_token",
        value="",
        expires=0,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/auth/refresh",
    )
    # Also clear legacy cookie scoped to /auth
    response.set_cookie(
        "refresh_token",
        value="",
        expires=0,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/auth",
    )
    return response


def set_access_cookie(response, token: str):
    secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    issuer, audience, access_ttl, _ = _jwt_settings()
    response.set_cookie(
        "access_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/",
        max_age=access_ttl,
    )
    return response


def clear_access_cookie(response):
    secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    response.set_cookie(
        "access_token",
        value="",
        expires=0,
        httponly=True,
        secure=secure,
        samesite="Strict",
        path="/",
    )
    return response


def requires_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
        if not token:
            token = request.cookies.get("access_token")

        if not token:
            return _handle_auth_failure("missing access token")

        try:
            claims = verify_access_jwt(token)
            g.user_id = claims.get("sub")
            g.jwt_claims = claims
            resp = fn(*args, **kwargs)
            return resp
        except jwt.ExpiredSignatureError:
            # Attempt refresh using stateless refresh JWT
            refresh_token = request.cookies.get("refresh_token")
            if not refresh_token:
                return _handle_auth_failure("invalid or expired token")

            try:
                # Verify refresh token (stateless)
                refresh_claims = verify_refresh_jwt(refresh_token)
                user_id = refresh_claims.get("sub")

                # Generate new tokens (token rotation)
                new_access_token = generate_access_jwt(user_id)
                new_refresh_token = generate_refresh_jwt(user_id)

                # Set user context for the request
                g.user_id = user_id
                g.jwt_claims = None

                # Call the view and attach new cookies to response
                resp = fn(*args, **kwargs)
                resp = make_response(resp)
                set_refresh_cookie(resp, new_refresh_token)
                set_access_cookie(resp, new_access_token)
                return resp

            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                return _handle_auth_failure("invalid or expired token")
            except Exception:
                return _handle_auth_failure("invalid or expired token")
        except Exception:
            return _handle_auth_failure("invalid or expired token")

    return wrapper


def _handle_auth_failure(error_msg: str):
    """Handle authentication failures - redirect HTML requests, return JSON for API requests."""
    # Check if this is an API request (JSON expected) or HTML page request
    if request.is_json or request.headers.get("Accept", "").startswith(
        "application/json"
    ):
        return jsonify({"error": error_msg}), 401
    else:
        # For HTML page requests, redirect to home page (where login modal can be shown)
        from flask import redirect, flash

        flash("Please log in to access this page", "error")
        return redirect("/")  # Redirect to home page instead of showing JSON error
