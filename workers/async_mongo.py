import os
from pymongo import AsyncMongoClient
from dotenv import load_dotenv

_client = None
_db = None

load_dotenv(override=True)


async def init_async_db(uri=None, db_name=None):
    global _client, _db
    uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
    db_name = db_name or os.environ.get("MONGO_DB_NAME", "url-shortener")
    _client = AsyncMongoClient(uri)
    # Explicitly connect
    await _client.aconnect()
    _db = _client[db_name]


async def get_async_db():
    if _db is None:
        await init_async_db()
    return _db
