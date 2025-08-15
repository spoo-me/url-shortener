from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, g, render_template

from .limiter import limiter
from utils.auth_utils import (
	verify_password,
	hash_password,
	generate_access_jwt,
	create_refresh_token,
	set_refresh_cookie,
	set_access_cookie,
	clear_refresh_cookie,
	clear_access_cookie,
	requires_auth,
)
from utils.mongo_utils import (
	get_user_by_email,
	get_user_by_id,
	insert_refresh_token,
	find_refresh_token_by_hash,
	revoke_refresh_token,
)
from utils.url_utils import get_client_ip
import hashlib
from utils.mongo_utils import users_collection


auth = Blueprint("auth", __name__)


def _minimal_user_profile(user_doc):
	return {
		"id": str(user_doc["_id"]),
		"email": user_doc.get("email"),
		"user_name": user_doc.get("user_name"),
		"plan": user_doc.get("plan", "free"),
	}


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
	if not user or not user.get("password"):
		# Do not reveal which part failed
		return jsonify({"error": "invalid credentials"}), 401

	if not verify_password(password, user["password"]):
		return jsonify({"error": "invalid credentials"}), 401

	access_token = generate_access_jwt(str(user["_id"]))
	refresh_token, token_hash, refresh_ttl = create_refresh_token()
	insert_refresh_token(
		user_id=user["_id"],
		token_hash=token_hash,
		expires_at=datetime.now(timezone.utc) + timedelta(seconds=refresh_ttl),
		created_ip=get_client_ip(),
		user_agent=request.headers.get("User-Agent"),
	)
	resp = jsonify({"access_token": access_token, "user": _minimal_user_profile(user)})
	set_refresh_cookie(resp, refresh_token)
	set_access_cookie(resp, access_token)
	return resp, 200


@auth.route("/auth/refresh", methods=["POST"])
@limiter.limit("20/minute")
def refresh():
	refresh_token = request.cookies.get("refresh_token")
	if not refresh_token:
		return jsonify({"error": "missing refresh token"}), 401

	# Verify token exists in DB and not revoked/expired
	token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
	token_doc = find_refresh_token_by_hash(token_hash)
	if not token_doc or token_doc.get("revoked"):
		return jsonify({"error": "invalid refresh token"}), 401
	if token_doc.get("expires_at") and token_doc["expires_at"] < datetime.now(timezone.utc):
		return jsonify({"error": "refresh token expired"}), 401

	# Rotate token: revoke old, create new
	revoke_refresh_token(token_hash)
	new_refresh, new_hash, refresh_ttl = create_refresh_token()
	insert_refresh_token(
		user_id=token_doc["user_id"],
		token_hash=new_hash,
		expires_at=datetime.now(timezone.utc) + timedelta(seconds=refresh_ttl),
		created_ip=get_client_ip(),
		user_agent=request.headers.get("User-Agent"),
	)
	access_token = generate_access_jwt(str(token_doc["user_id"]))
	resp = jsonify({"access_token": access_token})
	set_refresh_cookie(resp, new_refresh)
	set_access_cookie(resp, access_token)
	return resp, 200


@auth.route("/auth/logout", methods=["POST"])
@limiter.limit("60/hour")
def logout():
	refresh_token = request.cookies.get("refresh_token")
	resp = jsonify({"success": True})
	if refresh_token:
		token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
		revoke_refresh_token(token_hash, hard_delete=True)
	clear_refresh_cookie(resp)
	clear_access_cookie(resp)
	return resp, 200


@auth.route("/auth/me", methods=["GET"])
@requires_auth
def me():
	user_id = g.user_id
	user = get_user_by_id(user_id)
	if not user:
		return jsonify({"error": "user not found"}), 404
	return jsonify({"user": _minimal_user_profile(user)})


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
	if len(password) < 8:
		return jsonify({"error": "password must be at least 8 characters"}), 400

	# Check existing user
	existing = get_user_by_email(email)
	if existing:
		return jsonify({"error": "email already registered"}), 409
	
	password_hash = hash_password(password)
	user_doc = {
		"email": email,
		"password": password_hash,
		"user_name": user_name,
		"plan": "free",
		"signup_ip": get_client_ip(),
		"created_at": datetime.now(timezone.utc),
		"updated_at": datetime.now(timezone.utc),
	}
	try:
		insert_result = users_collection.insert_one(user_doc)
		user_id = insert_result.inserted_id
	except Exception:
		return jsonify({"error": "failed to create user"}), 500

	# Issue tokens just like login
	access_token = generate_access_jwt(str(user_id))
	refresh_token, token_hash, refresh_ttl = create_refresh_token()
	insert_refresh_token(
		user_id=user_id,
		token_hash=token_hash,
		expires_at=datetime.now(timezone.utc) + timedelta(seconds=refresh_ttl),
		created_ip=get_client_ip(),
		user_agent=request.headers.get("User-Agent"),
	)
	resp = jsonify({
		"access_token": access_token,
		"user": _minimal_user_profile({"_id": user_id, **user_doc}),
	})
	set_refresh_cookie(resp, refresh_token)
	set_access_cookie(resp, access_token)
	return resp, 201


@auth.route("/dashboard", methods=["GET"])
@requires_auth
def dashboard():
	user = get_user_by_id(g.user_id)
	print(user)
	if not user:
		return jsonify({"error": "user not found"}), 404
	return render_template(
		"dashboard.html",
		host_url=request.host_url,
		user=_minimal_user_profile(user),
	)


