from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
import os
import re
from bson import ObjectId
from utils.url_utils import validate_emoji_alias

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
clicks_collection = db["clicks"]
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


def get_user_by_oauth_provider(provider, provider_user_id, projection=None):
    """Get user by OAuth provider and provider user ID"""
    try:
        user = users_collection.find_one(
            {
                "auth_providers.provider": provider,
                "auth_providers.provider_user_id": provider_user_id,
            },
            projection,
        )
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


def update_url_v2_clicks(url_id, last_click_time=None, increment_clicks=1):
    """Atomically update total_clicks and last_click for a URL V2 document"""
    try:
        from datetime import datetime, timezone

        result = urls_v2_collection.update_one(
            {"_id": url_id},
            {
                "$inc": {"total_clicks": increment_clicks},
                "$set": {"last_click": last_click_time or datetime.now(timezone.utc)},
            },
        )
        return result
    except Exception:
        return None


def expire_url_if_max_clicks_reached(url_id, max_clicks):
    """Conditionally expire URL if max_clicks is reached"""
    try:
        result = urls_v2_collection.update_one(
            {"_id": ObjectId(url_id), "total_clicks": {"$gte": max_clicks}},
            {"$set": {"status": "EXPIRED"}},
        )
        return result
    except Exception:
        return None


def insert_click_data(click_data):
    """Insert click data into the time-series clicks collection"""
    try:
        # Ensure proper time-series schema with meta field
        if "meta" not in click_data:
            print("[MongoDB] Warning: click_data missing 'meta' field")
            return False

        if "clicked_at" not in click_data:
            print("[MongoDB] Warning: click_data missing 'clicked_at' field")
            return False

        clicks_collection.insert_one(click_data)
        return True
    except Exception as e:
        print(f"[MongoDB] Error inserting click data: {e}")
        return False


def get_url_by_length_and_type(short_code):
    """Determine URL schema based on length and fetch from appropriate collection"""
    # First check if it's an emoji
    if validate_emoji_alias(short_code):
        return load_emoji_url(short_code), "emoji"

    # Check length: 7 chars typically URLsV2, 6 chars typically old URLs
    if len(short_code) == 7:
        # Try URLsV2 first
        url_data = get_url_v2_by_alias(short_code)
        if url_data:
            return url_data, "v2"
        # Fallback to old schema
        url_data = load_url(short_code)
        if url_data:
            return url_data, "v1"
    elif len(short_code) == 6:
        # Try old schema first
        url_data = load_url(short_code)
        if url_data:
            return url_data, "v1"
        # Fallback to URLsV2 (custom aliases)
        url_data = get_url_v2_by_alias(short_code)
        if url_data:
            return url_data, "v2"
    else:
        # For other lengths, try both (custom aliases)
        url_data = get_url_v2_by_alias(short_code)
        if url_data:
            return url_data, "v2"
        url_data = load_url(short_code)
        if url_data:
            return url_data, "v1"

    return None, None


def get_url_v2_by_id(url_id, projection=None):
    """Get a URL V2 document by its MongoDB ObjectId"""
    try:
        from bson import ObjectId

        if isinstance(url_id, str):
            url_id = ObjectId(url_id)
        return urls_v2_collection.find_one({"_id": url_id}, projection)
    except Exception:
        return None


def validate_url_ownership(url_id, owner_id):
    """Validate that a URL belongs to the specified owner"""
    try:
        from bson import ObjectId

        if isinstance(url_id, str):
            url_id = ObjectId(url_id)
        if isinstance(owner_id, str):
            owner_id = ObjectId(owner_id)

        url_doc = urls_v2_collection.find_one(
            {"_id": url_id, "owner_id": owner_id}, {"_id": 1}
        )
        return url_doc is not None
    except Exception:
        return False


def check_url_stats_privacy(short_code):
    """Check if a URL's statistics are private or public

    Returns:
        dict: {"private": bool, "owner_id": str|None, "exists": bool}
    """
    try:
        # First try V2 URLs (new schema)
        url_doc = get_url_v2_by_alias(short_code, {"private_stats": 1, "owner_id": 1})
        if url_doc:
            private_stats = url_doc.get(
                "private_stats", True
            )  # Default to private if not set
            owner_id = str(url_doc.get("owner_id")) if url_doc.get("owner_id") else None
            return {"private": private_stats, "owner_id": owner_id, "exists": True}

        # Fallback to V1 URLs (old schema) - these don't have private_stats field
        # so they are considered public by default for backward compatibility
        url_doc = load_url(short_code)
        if url_doc:
            return {"private": False, "owner_id": None, "exists": True}

        # URL doesn't exist
        return {"private": False, "owner_id": None, "exists": False}
    except Exception:
        return {"private": True, "owner_id": None, "exists": False}  # Fail safe


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

        # OAuth provider indexes
        users_collection.create_index(
            [
                ("auth_providers.provider", ASCENDING),
                ("auth_providers.provider_user_id", ASCENDING),
            ],
            unique=True,
            sparse=True,
        )
        users_collection.create_index([("auth_providers.provider", ASCENDING)])

        # v2 urls indexes
        urls_v2_collection.create_index([("alias", ASCENDING)], unique=True)
        urls_v2_collection.create_index([("owner_id", ASCENDING)])
        urls_v2_collection.create_index(
            [
                ("owner_id", ASCENDING),
                ("created_at", DESCENDING),
            ]
        )
        urls_v2_collection.create_index([("total_clicks", DESCENDING)])
        urls_v2_collection.create_index([("last_click", DESCENDING)])

        # Create time-series collection for clicks if it doesn't exist
        try:
            db.create_collection(
                "clicks",
                timeseries={
                    "timeField": "clicked_at",
                    "metaField": "meta",
                    "granularity": "seconds",
                },
            )
        except Exception:
            # Collection may already exist, that's fine
            pass

        # clicks collection indexes (time-series)
        clicks_collection.create_index(
            [
                ("meta.url_id", ASCENDING),
                ("clicked_at", DESCENDING),
            ]
        )
        clicks_collection.create_index([("clicked_at", DESCENDING)])

        # api keys indexes
        api_keys_collection.create_index([("user_id", ASCENDING)])
        api_keys_collection.create_index([("token_hash", ASCENDING)], unique=True)
        # Optional TTL: remove when expires_at passes
        api_keys_collection.create_index(
            [("expires_at", ASCENDING)], expireAfterSeconds=0
        )
    except Exception:
        pass
