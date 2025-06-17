from flask_limiter import Limiter
from utils.mongo_utils import MONGO_URI, ip_bypasses
from utils.url_utils import get_client_ip
from flask import request

limiter = Limiter(
    key_func=get_client_ip,  # Use custom function that handles Cloudflare/proxy headers
    default_limits=["5 per minute", "500 per day", "50 per hour"],
    storage_uri=MONGO_URI,
    strategy="fixed-window",
)


@limiter.request_filter
def ip_whitelist():
    if request.method == "GET":
        return True

    bypasses = ip_bypasses.find()
    bypasses = [doc["_id"] for doc in bypasses]

    client_ip = get_client_ip()
    return client_ip in bypasses
