import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import request, jsonify, g
import jwt
from argon2 import PasswordHasher


password_hasher = PasswordHasher()


def _use_rs256() -> bool:
	return bool(os.getenv("JWT_PRIVATE_KEY") and os.getenv("JWT_PUBLIC_KEY"))


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
			raise RuntimeError("JWT_SECRET must be set when RS256 keys are not provided")
		return (secret, secret)


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
	return jwt.decode(token, public_key, algorithms=[algorithm], audience=audience, issuer=issuer)


def create_refresh_token() -> tuple[str, str, int]:
	"""Return (token, token_hash, max_age_seconds)."""
	*_, refresh_ttl = _jwt_settings()
	token = secrets.token_urlsafe(64)
	hash_hex = hashlib.sha256(token.encode("utf-8")).hexdigest()
	return token, hash_hex, refresh_ttl


def set_refresh_cookie(response, token: str):
	secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
	*_, refresh_ttl = _jwt_settings()
	response.set_cookie(
		"refresh_token",
		value=token,
		httponly=True,
		secure=secure,
		samesite="Strict",
		path="/auth/refresh",
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
		path="/auth/refresh",
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
			return jsonify({"error": "missing access token"}), 401
		try:
			claims = verify_access_jwt(token)
			g.user_id = claims.get("sub")
			g.jwt_claims = claims
		except Exception:
			return jsonify({"error": "invalid or expired token"}), 401
		return fn(*args, **kwargs)

	return wrapper


