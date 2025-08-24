import time
from bson import ObjectId
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
)
from utils.url_utils import (
    BOT_USER_AGENTS,
    get_country,
    get_client_ip,
)
from utils.mongo_utils import (
    update_url,
    update_emoji_url,
    get_url_by_length_and_type,
    update_url_v2_clicks,
    expire_url_if_max_clicks_reached,
    insert_click_data,
)
from utils.auth_utils import verify_password
from cache import cache_query as cq
from cache.cache_url import UrlCacheData

from .limiter import limiter

from ua_parser import parse
from datetime import datetime, timezone
from urllib.parse import unquote
import re
import tldextract
from crawlerdetect import CrawlerDetect

crawler_detect = CrawlerDetect()
tld_no_cache_extract = tldextract.TLDExtract(cache_dir=None)

url_redirector = Blueprint("url_redirector", __name__)


@url_redirector.route("/<short_code>", methods=["GET"])
@limiter.exempt
def redirect_url(short_code):
    user_ip = get_client_ip()
    short_code = unquote(short_code)
    start_time = time.perf_counter()

    # Try to get URL data from cache first (new cache schema)
    cached_url_data = cq.get_url_cache_data(short_code)

    if cached_url_data:
        url_data = {
            "_id": cached_url_data._id,
            "url": cached_url_data.long_url,
            "long_url": cached_url_data.long_url,
            "password": cached_url_data.password_hash,
            "block-bots": cached_url_data.block_bots,
            "expiration-time": cached_url_data.expiration_time,
            "expire_after": cached_url_data.expiration_time,
            "status": cached_url_data.url_status,
            # Add missing fields that might be needed for v2 URLs
            "max_clicks": cached_url_data.max_clicks,  # Not cached for performance
            "owner_id": cached_url_data.owner_id,
        }
        schema_type = cached_url_data.schema_version

        if schema_type == "v2":
            url_data["_id"] = ObjectId(cached_url_data._id)
            url_data["owner_id"] = (
                ObjectId(cached_url_data.owner_id) if cached_url_data.owner_id else None
            )
            if (
                url_data["max_clicks"] is not None
                and type(url_data["max_clicks"]) is not int
            ):
                url_data["max_clicks"] = int(url_data["max_clicks"])

        is_emoji = False
    else:
        # Determine URL schema and fetch data
        url_data, schema_type = get_url_by_length_and_type(short_code)
        is_emoji = schema_type == "emoji"

        if not url_data:
            return (
                render_template(
                    "error.html",
                    error_code="404",
                    error_message="URL NOT FOUND",
                    host_url=request.host_url,
                ),
                404,
            )

        # Cache the URL data (but only if it should be cached)
        # For v2 URLs, check status and don't cache if blocked/expired/inactive
        if schema_type == "v2":
            status = url_data.get("status", "ACTIVE")
            if status in ["BLOCKED", "EXPIRED", "INACTIVE"]:
                # Cache minimal data for blocked/expired/inactive URLs
                minimal_cache = UrlCacheData(
                    _id=str(url_data["_id"]),
                    alias=short_code,
                    long_url="",
                    block_bots=False,
                    password_hash=None,
                    expiration_time=None,
                    max_clicks=None,
                    url_status=status,
                    schema_version="v2",
                    owner_id=str(url_data.get("owner_id"))
                    if url_data.get("owner_id")
                    else None,
                )
                cq.set_url_cache_data(short_code, minimal_cache)
            else:
                cache_data = UrlCacheData(
                    _id=str(url_data["_id"]),
                    alias=short_code,
                    long_url=url_data["long_url"],
                    block_bots=url_data.get("block_bots", False),
                    password_hash=url_data.get("password"),
                    expiration_time=url_data.get("expire_after"),
                    max_clicks=url_data.get("max_clicks"),
                    url_status=status,
                    schema_version="v2",
                    owner_id=str(url_data.get("owner_id"))
                    if url_data.get("owner_id")
                    else None,
                )
                cq.set_url_cache_data(short_code, cache_data)
        elif schema_type == "v1":
            # Cache old schema URLs without max-clicks
            if not url_data.get("max-clicks"):
                cache_data = UrlCacheData(
                    _id=short_code,  # For v1, _id is the short_code
                    alias=short_code,
                    long_url=url_data["url"],
                    block_bots=url_data.get("block-bots", False),
                    password_hash=url_data.get("password"),
                    expiration_time=url_data.get("expiration-time"),
                    max_clicks=url_data.get("max-clicks"),
                    url_status="ACTIVE",  # v1 URLs don't have status field
                    schema_version="v1",
                    owner_id=None,  # v1 URLs don't have owner_id
                )
                cq.set_url_cache_data(short_code, cache_data)

    # Handle blocked/expired/inactive URLs for v2 schema
    if schema_type == "v2":
        status = url_data.get("status", "ACTIVE")
        if status in ["BLOCKED", "EXPIRED", "INACTIVE"]:
            return (
                render_template(
                    "error.html",
                    error_code="403" if status == "BLOCKED" else "400",
                    error_message="ACCESS DENIED"
                    if status == "BLOCKED"
                    else "SHORT URL EXPIRED",
                    host_url=request.host_url,
                ),
                403 if status == "BLOCKED" else 400,
            )

    # Get the URL to redirect to
    if schema_type == "v2":
        url = url_data["long_url"]
    else:
        url = url_data["url"]

    # Check max clicks for old schema
    if schema_type == "v1" and "max-clicks" in url_data:
        if int(url_data.get("total-clicks", 0)) >= int(url_data["max-clicks"]):
            return (
                render_template(
                    "error.html",
                    error_code="400",
                    error_message="SHORT URL EXPIRED",
                    host_url=request.host_url,
                ),
                400,
            )

    # Check password protection
    if "password" in url_data and url_data["password"]:
        password = request.values.get("password")

        # Use different password verification logic based on schema type
        password_valid = False
        if schema_type == "v2":
            # For v2 URLs, use verify_password for hashed passwords
            password_valid = verify_password(password or "", url_data["password"])
        else:
            # For v1 URLs, use direct string comparison
            password_valid = password == url_data["password"]

        if not password_valid:
            return (
                render_template(
                    "password.html", short_code=short_code, host_url=request.host_url
                ),
                401,
            )

    # Process the click and track analytics
    success = process_url_click(
        url_data, short_code, schema_type, is_emoji, user_ip, start_time
    )

    if not success:
        return jsonify({
            "error_code": "500",
            "error_message": "Internal server error",
            "host_url": request.host_url,
        }), 500

    return redirect(url)


def process_url_click(url_data, short_code, schema_type, is_emoji, user_ip, start_time):
    """Process click tracking and analytics for both v1 and v2 schemas"""
    try:
        if schema_type == "v2":
            return handle_v2_click(url_data, short_code, user_ip, start_time)
        else:
            return handle_legacy_click(
                url_data, short_code, is_emoji, user_ip, start_time
            )
    except Exception as e:
        print(f"Error processing click for {short_code}: {e}")
        return False


def handle_v2_click(url_data, short_code, user_ip, start_time):
    """Handle click tracking for new v2 schema URLs"""
    try:
        # Get user agent info
        user_agent = request.headers.get("User-Agent", "")
        if not user_agent:
            return False

        ua = parse(user_agent)
        if not ua or not ua.user_agent or not ua.os:
            return False

        os_name = ua.os.family
        browser = ua.user_agent.family
        device = ua.device.family if ua.device else "Unknown"

        print(ua.device)

        referrer = request.headers.get("Referer")
        country = get_country(user_ip)

        # Calculate redirect time in milliseconds
        redirect_ms = int((time.perf_counter() - start_time) * 1000)

        # Check if it's a bot
        is_bot = crawler_detect.isCrawler(user_agent) or any(
            re.search(bot, user_agent, re.IGNORECASE) for bot in BOT_USER_AGENTS
        )
        bot_name = None
        if is_bot:
            # Try to identify specific bot
            for bot in BOT_USER_AGENTS:
                if re.search(bot, user_agent, re.IGNORECASE):
                    bot_name = bot
                    break
            if not bot_name and crawler_detect.isCrawler(user_agent):
                bot_name = "crawler"

        # Prepare click data for time-series collection following agreed schema
        click_data = {
            "clicked_at": datetime.now(timezone.utc),  # timestamp field for time-series
            "meta": {  # meta field for time-series
                "url_id": url_data["_id"],
                "short_code": short_code,
                "owner_id": url_data.get("owner_id"),
            },
            "ip_address": user_ip,
            "country": country or "Unknown",
            "city": None,  # TODO: Implement city detection if needed
            "browser": browser,
            "os": os_name,
            "device": device,
            "redirect_ms": redirect_ms,
            "referrer": referrer,  # nullable
            "bot_name": bot_name,  # nullable
        }

        # Insert click data into time-series collection
        success = insert_click_data(click_data)
        if not success:
            print(f"Failed to insert click data for {short_code}")

        # Update URLsV2 document atomically with new fields
        current_time = datetime.now(timezone.utc)
        update_result = update_url_v2_clicks(
            url_data["_id"], last_click_time=current_time
        )

        # Check if URL should be expired due to max_clicks
        if url_data.get("max_clicks"):
            expire_result = expire_url_if_max_clicks_reached(
                url_data["_id"], url_data["max_clicks"]
            )
            if expire_result.modified_count > 0:
                # invalidate the cache
                cq.invalidate_url_cache(short_code)

        return update_result.acknowledged
    except Exception as e:
        print(f"Error handling v2 click: {e}")
        return False


def handle_legacy_click(url_data, short_code, is_emoji, user_ip, start_time):
    """Handle click tracking for legacy v1 schema URLs and emojis"""
    try:
        # Get user agent info
        user_agent = request.headers.get("User-Agent", "")
        if not user_agent:
            return False

        ua = parse(user_agent)
        if not ua or not ua.user_agent or not ua.os:
            return False

        os_name = ua.os.family
        browser = ua.user_agent.family
        referrer = request.headers.get("Referer")
        country = get_country(user_ip)

        if country:
            country = country.replace(".", " ")

        # Build update document for legacy schema
        updates = {"$inc": {}, "$set": {}, "$addToSet": {}}

        # Handle referrer tracking
        if referrer:
            referrer_raw = tld_no_cache_extract(referrer)
            referrer_domain = (
                f"{referrer_raw.domain}.{referrer_raw.suffix}"
                if referrer_raw.suffix
                else referrer_raw.domain
            )
            sanitized_referrer = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", referrer_domain)
            updates["$inc"][f"referrer.{sanitized_referrer}.counts"] = 1
            updates["$addToSet"][f"referrer.{sanitized_referrer}.ips"] = user_ip

        # Track analytics
        updates["$inc"][f"country.{country}.counts"] = 1
        updates["$addToSet"][f"country.{country}.ips"] = user_ip
        updates["$inc"][f"browser.{browser}.counts"] = 1
        updates["$addToSet"][f"browser.{browser}.ips"] = user_ip
        updates["$inc"][f"os_name.{os_name}.counts"] = 1
        updates["$addToSet"][f"os_name.{os_name}.ips"] = user_ip

        # Bot detection and blocking
        for bot in BOT_USER_AGENTS:
            if re.search(bot, user_agent, re.IGNORECASE):
                if url_data.get("block-bots", False):
                    return False  # Bot blocked
                sanitized_bot = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", bot)
                updates["$inc"][f"bots.{sanitized_bot}"] = 1
                break
        else:
            if crawler_detect.isCrawler(user_agent):
                if url_data.get("block-bots", False):
                    return False  # Bot blocked
                updates["$inc"][f"bots.{crawler_detect.getMatches()}"] = 1

        # Daily counters
        today = str(datetime.now()).split()[0]
        updates["$inc"][f"counter.{today}"] = 1

        # Check for unique click
        is_unique_click = user_ip not in url_data.get("ips", [])
        if is_unique_click:
            updates["$inc"][f"unique_counter.{today}"] = 1

        updates["$addToSet"]["ips"] = user_ip
        updates["$inc"]["total-clicks"] = 1

        # Last click info
        current_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        updates["$set"]["last-click"] = current_time_str
        updates["$set"]["last-click-browser"] = browser
        updates["$set"]["last-click-os"] = os_name
        updates["$set"]["last-click-country"] = country

        # Calculate and update average redirection time
        end_time = time.perf_counter()
        redirection_time = (end_time - start_time) * 1000
        curr_avg = url_data.get("average_redirection_time", 0)
        alpha = 0.1
        updates["$set"]["average_redirection_time"] = round(
            (1 - alpha) * curr_avg + alpha * redirection_time, 2
        )

        # Update the database
        if is_emoji:
            update_emoji_url(short_code, updates)
        else:
            update_url(short_code, updates)

        return True
    except Exception as e:
        print(f"Error handling legacy click: {e}")
        return False


@url_redirector.route("/<short_code>/password", methods=["POST"])
@limiter.exempt
def check_password(short_code):
    short_code = unquote(short_code)
    # TODO: Fetch from cache
    url_data, schema_type = get_url_by_length_and_type(short_code)

    if url_data:
        # Check if the URL is password protected
        password_field = "password"
        if password_field in url_data and url_data[password_field]:
            password = request.form.get("password")

            # Use different password verification logic based on schema type
            password_valid = False
            if schema_type == "v2":
                # For v2 URLs, use verify_password for hashed passwords
                password_valid = verify_password(
                    password or "", url_data[password_field]
                )
            else:
                # For v1 URLs, use direct string comparison
                password_valid = password == url_data[password_field]

            if password_valid:
                return redirect(f"{request.host_url}{short_code}?password={password}")
            else:
                # Show error message for incorrect password
                return render_template(
                    "password.html",
                    short_code=short_code,
                    error="Incorrect password",
                    host_url=request.host_url,
                )
        else:
            # URL exists but is not password protected
            return (
                render_template(
                    "error.html",
                    error_code="400",
                    error_message="Invalid short code or URL not password-protected",
                    host_url=request.host_url,
                ),
                400,
            )

    # URL not found
    return (
        render_template(
            "error.html",
            error_code="400",
            error_message="Invalid short code or URL not password-protected",
            host_url=request.host_url,
        ),
        400,
    )
