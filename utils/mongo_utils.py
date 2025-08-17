from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
import os
import re
from bson import ObjectId

load_dotenv(override=True)

MONGO_URI = os.environ["MONGODB_URI"]

client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("[MongoDB] Connected successfully")
except Exception as e:
    print(f"[MongoDB] Connection failed: {e}")

db = client["url-shortener"]

urls_collection = db["urls"]
urls_v2_collection = db["urlsV2"]
blocked_urls_collection = db["blocked-urls"]
emoji_urls_collection = db["emojis"]
ip_bypasses = db["ip-exceptions"]
users_collection = db["users"]
api_keys_collection = db["api-keys"]


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


# ===== API Keys helpers =====


def insert_api_key(doc: dict):
    try:
        result = api_keys_collection.insert_one(doc)
        return result.inserted_id
    except Exception:
        return None


def find_api_key_by_hash(token_hash: str, projection=None):
    try:
        doc = api_keys_collection.find_one({"token_hash": token_hash}, projection)
        return doc
    except Exception:
        return None


def list_api_keys_by_user(user_id, projection=None):
    try:
        uid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
        cur = api_keys_collection.find({"user_id": uid}, projection).sort(
            "created_at", ASCENDING
        )
        return list(cur)
    except Exception:
        return []


def revoke_api_key_by_id(user_id, key_id, *, hard_delete: bool = False) -> bool:
    try:
        uid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id
        kid = ObjectId(key_id) if not isinstance(key_id, ObjectId) else key_id
        if hard_delete:
            result = api_keys_collection.delete_one({"_id": kid, "user_id": uid})
            return result.deleted_count == 1
        else:
            result = api_keys_collection.update_one(
                {"_id": kid, "user_id": uid}, {"$set": {"revoked": True}}
            )
            return result.modified_count == 1
    except Exception:
        return False


def ensure_indexes():
    try:
        users_collection.create_index([("email", ASCENDING)], unique=True)
        # v2 urls indexes
        urls_v2_collection.create_index([("alias", ASCENDING)], unique=True)
        urls_v2_collection.create_index([("owner_id", ASCENDING)])
        urls_v2_collection.create_index(
            [("owner_id", ASCENDING), ("created_at", DESCENDING)]
        )
        # api keys indexes
        api_keys_collection.create_index([("user_id", ASCENDING)])
        api_keys_collection.create_index([("token_hash", ASCENDING)], unique=True)
        # Optional TTL: remove when expires_at passes
        api_keys_collection.create_index(
            [("expires_at", ASCENDING)], expireAfterSeconds=0
        )
    except Exception:
        pass
