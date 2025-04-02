from pymongo import MongoClient
from dotenv import load_dotenv
import os
import re

load_dotenv(override=True)

MONGO_URI = os.environ["MONGODB_URI"]

client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("\n Pinged your deployment. You successfully connected to MongoDB! \n")
except Exception as e:
    print(e)

db = client["url-shortener"]

urls_collection = db["urls"]
blocked_urls_collection = db["blocked-urls"]
emoji_urls_collection = db["emojis"]
ip_bypasses = db["ip-exceptions"]


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


def alias_exists(slug) -> bool:
    """Returns True if the slug exists in the database, False otherwise."""
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


def emoji_exists(emoji_alias) -> bool:
    """Returns True if the emoji alias exists in the database, False otherwise."""
    try:
        emoji_data = emoji_urls_collection.find_one({"_id": emoji_alias})
    except Exception:
        emoji_data = None
    return emoji_data is not None


def validate_blocked_url(url) -> bool:
    blocked_urls = blocked_urls_collection.find()
    blocked_urls = [doc["_id"] for doc in blocked_urls]

    for blocked_url in blocked_urls:
        if re.match(blocked_url, url):
            return False

    return True
