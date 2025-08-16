from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv
import os
import re
from bson import ObjectId

load_dotenv(override=True)

MONGO_URI = os.environ["MONGODB_URI"]

client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

db = client["url-shortener"]

urls_collection = db["urls"]
urls_v2_collection = db["urlsV2"]
blocked_urls_collection = db["blocked-urls"]
emoji_urls_collection = db["emojis"]
ip_bypasses = db["ip-exceptions"]
users_collection = db["users"]
refresh_tokens_collection = db["refresh-tokens"]


def load_url(id, projection=None):
    try:
        url_data = urls_collection.find_one({"_id": id}, projection)
    except Exception:
        url_data = None
    return url_data


def aggregate_url(pipeline):
    try:
        url_data = urls_collection.aggregate(pipeline)
        url_data = list(url_data)[0]
    except Exception:
        url_data = None
    return url_data


def insert_url(id, url_data):
    try:
        urls_collection.insert_one({"_id": id, **url_data})
    except Exception:
        pass


def update_url(id, updates):
    try:
        urls_collection.update_one({"_id": id}, updates)
    except Exception:
        pass


def check_if_slug_exists(slug):
    projection = {"_id": 1}
    try:
        url_data = urls_collection.find_one({"_id": slug}, projection)
    except Exception:
        url_data = None
    return url_data is not None


def load_emoji_url(alias, projection=None):
    try:
        emoji_data = emoji_urls_collection.find_one({"_id": alias}, projection)
    except Exception:
        emoji_data = None
    return emoji_data


def aggregate_emoji_url(pipeline):
    try:
        emoji_data = emoji_urls_collection.aggregate(pipeline)
        emoji_data = list(emoji_data)[0]
    except Exception:
        emoji_data = None
    return emoji_data


def insert_emoji_url(alias, emoji_data):
    try:
        emoji_urls_collection.insert_one({"_id": alias, **emoji_data})
    except Exception:
        pass


def update_emoji_url(alias, updates):
    try:
        emoji_urls_collection.update_one({"_id": alias}, updates)
    except Exception:
        pass


def check_if_emoji_alias_exists(emoji_alias):
    try:
        emoji_data = emoji_urls_collection.find_one({"_id": emoji_alias})
    except Exception:
        emoji_data = None
    return emoji_data is not None


def validate_blocked_url(url):
    blocked_urls = blocked_urls_collection.find()
    blocked_urls = [doc["_id"] for doc in blocked_urls]

    for blocked_url in blocked_urls:
        if re.match(blocked_url, url):
            return False

    return True


def get_user_by_email(email, projection=None):
    try:
        user = users_collection.find_one({"email": email}, projection)
    except Exception:
        user = None
    return user


def get_user_by_id(user_id, projection=None):
    try:
        user = users_collection.find_one({"_id": ObjectId(user_id)}, projection)
    except Exception:
        user = None
    return user


def create_user(user_data):
    try:
        result = users_collection.insert_one(user_data)
        return result.inserted_id
    except Exception:
        return None


def update_user(user_id, updates):
    try:
        users_collection.update_one({"_id": user_id}, updates)
    except Exception:
        pass


def insert_refresh_token(
    user_id, token_hash, expires_at, created_ip=None, user_agent=None
):
    doc = {
        "user_id": user_id,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "created_at": None,
        "revoked": False,
        "created_ip": created_ip,
        "user_agent": user_agent,
    }
    try:
        from datetime import datetime, timezone

        doc["created_at"] = datetime.now(timezone.utc)
        refresh_tokens_collection.insert_one(doc)
    except Exception:
        pass


def find_refresh_token_by_hash(token_hash):
    try:
        token_doc = refresh_tokens_collection.find_one({"token_hash": token_hash})
    except Exception:
        token_doc = None
    return token_doc


def revoke_refresh_token(token_hash, *, hard_delete: bool = False):
    try:
        if hard_delete:
            refresh_tokens_collection.delete_one({"token_hash": token_hash})
        else:
            refresh_tokens_collection.update_one(
                {"token_hash": token_hash}, {"$set": {"revoked": True}}
            )
    except Exception:
        pass


def revoke_all_user_tokens(user_id):
    try:
        refresh_tokens_collection.update_many(
            {"user_id": user_id, "revoked": False}, {"$set": {"revoked": True}}
        )
    except Exception:
        pass


def ensure_indexes():
    try:
        users_collection.create_index([("email", ASCENDING)], unique=True)
        refresh_tokens_collection.create_index([("user_id", ASCENDING)])
        # TTL index: when expires_at passes, document will be removed
        refresh_tokens_collection.create_index(
            [("expires_at", ASCENDING)], expireAfterSeconds=0
        )
        # v2 urls indexes
        urls_v2_collection.create_index([("alias", ASCENDING)], unique=True)
        urls_v2_collection.create_index([("owner_id", ASCENDING)])
    except Exception:
        pass


# ===== v2 URL helpers =====


def insert_url_v2(doc: dict):
    try:
        urls_v2_collection.insert_one(doc)
    except Exception:
        pass


def get_url_v2_by_alias(alias: str, projection=None):
    try:
        return urls_v2_collection.find_one({"alias": alias}, projection)
    except Exception:
        return None


def check_if_v2_alias_exists(alias: str) -> bool:
    try:
        doc = urls_v2_collection.find_one({"alias": alias}, {"_id": 1})
        return doc is not None
    except Exception:
        return False
