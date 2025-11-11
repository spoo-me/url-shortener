import os
import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps, lru_cache
from typing import Any, Dict

from flask import request, jsonify, g, make_response
import jwt
from argon2 import PasswordHasher
from bson import ObjectId
from utils.mongo_utils import find_api_key_by_hash
from utils.logger import get_logger


password_hasher = PasswordHasher()
log = get_logger(__name__)


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


def generate_access_jwt(user_id: str, auth_method: str = "pwd") -> str:
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
        "amr": [auth_method],  # Authentication Methods References
    }
    return jwt.encode(claims, private_key, algorithm=algorithm)


def verify_access_jwt(token: str):
    issuer, audience, *_ = _jwt_settings()
    _, public_key = _jwt_keys()
    algorithm = "RS256" if _use_rs256() else "HS256"
    return jwt.decode(
        token, public_key, algorithms=[algorithm], audience=audience, issuer=issuer
    )


def generate_refresh_jwt(user_id: str, auth_method: str = "pwd") -> str:
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
        "amr": [auth_method],  # Authentication Methods References
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
        samesite="Lax",
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
        samesite="Lax",
        path="/",
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
        samesite="Lax",
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
        samesite="Lax",
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
            # Attempt refresh when access token is missing but refresh token exists
            refresh_token = request.cookies.get("refresh_token")
            if refresh_token:
                try:
                    refresh_claims = verify_refresh_jwt(refresh_token)
                    user_id = refresh_claims.get("sub")
                    new_access_token = generate_access_jwt(user_id)
                    new_refresh_token = generate_refresh_jwt(user_id)
                    g.user_id = user_id
                    g.jwt_claims = None
                    resp = fn(*args, **kwargs)
                    resp = make_response(resp)
                    set_refresh_cookie(resp, new_refresh_token)
                    set_access_cookie(resp, new_access_token)
                    return resp
                except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                    pass
                except Exception:
                    pass
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
    """Handle authentication failures: JSON for APIs, 401 HTML page for browser routes."""
    accept_header = request.headers.get("Accept", "")
    wants_json = (
        request.is_json
        or "application/json" in accept_header
        or request.path.startswith("/auth/")
    )
    if wants_json:
        return jsonify({"error": error_msg}), 401
    else:
        from flask import render_template

        return (
            render_template(
                "error.html",
                error_code="401",
                error_message=error_msg.upper(),
                host_url=request.host_url,
            ),
            401,
        )


def resolve_owner_id_from_request():
    """Resolve the authenticated user id from either API key or JWT.

    - API key: Authorization: Bearer spoo_<raw>
        - Validates revocation/expiry and sets g.api_key and request.api_key
        - Returns ObjectId of user
    - JWT: Authorization: Bearer <jwt> or access_token cookie
        - Returns ObjectId of user
    - Otherwise returns None
    """
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        # API key path: Authorization: Bearer spoo_<key>
        if token.startswith("spoo_"):
            raw = token[len("spoo_") :]
            token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            key_doc = find_api_key_by_hash(token_hash)
            now = datetime.now(timezone.utc)

            # Check if key exists
            if not key_doc:
                log.warning(
                    "api_key_invalid",
                    key_prefix=raw[:8] if len(raw) >= 8 else "short",
                    reason="not_found",
                )
                return None

            # Check if key is revoked
            if key_doc.get("revoked", False):
                log.warning(
                    "api_key_invalid",
                    key_prefix=key_doc.get("token_prefix", "unknown"),
                    key_id=str(key_doc.get("_id")),
                    user_id=str(key_doc.get("user_id")),
                    reason="revoked",
                )
                return None

            # Check if key is expired
            if key_doc.get("expires_at") and key_doc["expires_at"] <= now:
                log.warning(
                    "api_key_invalid",
                    key_prefix=key_doc.get("token_prefix", "unknown"),
                    key_id=str(key_doc.get("_id")),
                    user_id=str(key_doc.get("user_id")),
                    reason="expired",
                    expired_at=key_doc["expires_at"].isoformat(),
                )
                return None

            if (
                key_doc
                and not key_doc.get("revoked", False)
                and (not key_doc.get("expires_at") or key_doc["expires_at"] > now)
            ):
                # Attach scopes for downstream checks
                try:
                    g.api_key = key_doc  # type: ignore[attr-defined]
                except Exception:
                    pass
                try:
                    request.api_key = key_doc  # type: ignore[attr-defined]
                except Exception:
                    pass
                user_id = key_doc.get("user_id")
                try:
                    return (
                        ObjectId(user_id)
                        if not isinstance(user_id, ObjectId)
                        else user_id
                    )
                except Exception:
                    return None
    if not token:
        token = request.cookies.get("access_token")
    if token:
        try:
            claims = verify_access_jwt(token)
            user_id = claims.get("sub")
            return ObjectId(user_id)
        except Exception:
            pass
    return None


def get_user_profile(user_doc: Dict[str, Any]) -> Dict[str, Any]:
    """Create minimal user profile including OAuth provider info

    Args:
        user_doc: User document from database

    Returns:
        Minimal user profile dict
    """
    profile = {
        "id": str(user_doc["_id"]),
        "email": user_doc.get("email"),
        "email_verified": user_doc.get("email_verified", False),
        "user_name": user_doc.get("user_name"),
        "plan": user_doc.get("plan", "free"),
        "password_set": user_doc.get("password_set", False),
        "auth_providers": [],
    }

    # Add OAuth providers info (without sensitive data)
    auth_providers = user_doc.get("auth_providers", [])
    for provider in auth_providers:
        profile["auth_providers"].append(
            {
                "provider": provider.get("provider"),
                "email": provider.get("email"),
                "linked_at": provider.get("linked_at").isoformat()
                if provider.get("linked_at")
                else None,
            }
        )

    # Add profile picture info
    pfp = user_doc.get("pfp")
    if pfp:
        profile["pfp"] = {"url": pfp.get("url"), "source": pfp.get("source")}

    return profile
