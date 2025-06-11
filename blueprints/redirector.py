import time
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
    validate_emoji_alias,
)
from utils.mongo_utils import (
    load_url,
    update_url,
    load_emoji_url,
    update_emoji_url,
)
from cache import cache_query as cq
from cache.cache_url import UrlData

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
    projection = {
        "_id": 1,
        "url": 1,
        "password": 1,
        "max-clicks": 1,
        "expiration-time": 1,
        "total-clicks": 1,
        "ips": {"$elemMatch": {"$eq": user_ip}},
        "block-bots": 1,
        "average_redirection_time": 1,
    }

    short_code = unquote(short_code)

    is_emoji = False

    # Measure redirection time
    start_time = time.perf_counter()

    cached_url_data = cq.get_url_data(short_code)
    if cached_url_data:
        url_data = {
            "url": cached_url_data.url,
            "password": cached_url_data.password,
            "block-bots": cached_url_data.block_bots,
        }
    else:
        if validate_emoji_alias(short_code):
            is_emoji = True
            url_data = load_emoji_url(short_code, projection)
        else:
            url_data = load_url(short_code, projection)

        if url_data and not url_data.get(
            "max-clicks", 0
        ):  # skip caching if max-clicks is set (will break if url has high max-clicks)
            cq.set_url_data(
                short_code,
                UrlData(
                    url=url_data["url"],
                    short_code=short_code,
                    password=url_data.get("password"),
                    block_bots=url_data.get("block-bots", False),
                ),
            )

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

    url = url_data["url"]

    if "max-clicks" in url_data:
        if int(url_data["total-clicks"]) >= int(url_data["max-clicks"]):
            return (
                render_template(
                    "error.html",
                    error_code="400",
                    error_message="SHORT URL EXPIRED",
                    host_url=request.host_url,
                ),
                400,
            )

    if "password" in url_data:
        password = request.values.get("password")
        if password != url_data["password"]:
            return (
                render_template(
                    "password.html", short_code=short_code, host_url=request.host_url
                ),
                401,
            )

    # store the device and browser information
    user_agent = request.headers.get("User-Agent")
    if not user_agent:
        return jsonify(
            {
                "error_code": "400",
                "error_message": "Invalid User-Agent",
                "host_url": request.host_url,
            }
        ), 400

    try:
        ua = parse(user_agent)
        if not ua or not ua.user_agent or not ua.os:
            return jsonify(
                {
                    "error_code": "400",
                    "error_message": "Invalid User-Agent",
                    "host_url": request.host_url,
                }
            ), 400
    except Exception:
        return jsonify(
            {
                "error_code": "400",
                "error_message": "An internal error occurred while processing the User-Agent",
                "host_url": request.host_url,
            }
        ), 400

    os_name = ua.os.family
    browser = ua.user_agent.family
    referrer = request.headers.get("Referer")
    country = get_country(user_ip)

    is_unique_click = url_data.get("ips", None) is None

    if country:
        country = country.replace(".", " ")

    updates = {"$inc": {}, "$set": {}, "$addToSet": {}}

    if "ips" not in url_data:
        url_data["ips"] = []

    if referrer:
        referrer_raw = tld_no_cache_extract(referrer)
        referrer = (
            f"{referrer_raw.domain}.{referrer_raw.suffix}"
            if referrer_raw.suffix
            else referrer_raw.domain
        )
        sanitized_referrer = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", referrer)

        updates["$inc"][f"referrer.{sanitized_referrer}.counts"] = 1
        updates["$addToSet"][f"referrer.{sanitized_referrer}.ips"] = user_ip

    updates["$inc"][f"country.{country}.counts"] = 1
    updates["$addToSet"][f"country.{country}.ips"] = user_ip

    updates["$inc"][f"browser.{browser}.counts"] = 1
    updates["$addToSet"][f"browser.{browser}.ips"] = user_ip

    updates["$inc"][f"os_name.{os_name}.counts"] = 1
    updates["$addToSet"][f"os_name.{os_name}.ips"] = user_ip

    for bot in BOT_USER_AGENTS:
        bot_re = re.compile(bot, re.IGNORECASE)
        if bot_re.search(user_agent):
            if url_data.get("block-bots", False):
                return (
                    jsonify(
                        {
                            "error_code": "403",
                            "error_message": "Access Denied, Bots not allowed",
                            "host_url": request.host_url,
                        }
                    ),
                    403,
                )
            sanitized_bot = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", bot)
            updates["$inc"][f"bots.{sanitized_bot}"] = 1
            break
    else:
        if crawler_detect.isCrawler(user_agent):
            if url_data.get("block-bots", False):
                return (
                    jsonify(
                        {
                            "error_code": "403",
                            "error_message": "Access Denied, Bots not allowed",
                            "host_url": request.host_url,
                        }
                    ),
                    403,
                )
            updates["$inc"][f"bots.{crawler_detect.getMatches()}"] = 1

    # increment the counter for the short code
    today = str(datetime.now()).split()[0]
    updates["$inc"][f"counter.{today}"] = 1

    if is_unique_click:
        updates["$inc"][f"unique_counter.{today}"] = 1

    updates["$addToSet"]["ips"] = user_ip

    updates["$inc"]["total-clicks"] = 1

    updates["$set"]["last-click"] = str(
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    updates["$set"]["last-click-browser"] = browser
    updates["$set"]["last-click-os"] = os_name
    updates["$set"]["last-click-country"] = country

    # Calculate redirection time
    end_time = time.perf_counter()
    redirection_time = (end_time - start_time) * 1000

    curr_avg = url_data.get("average_redirection_time", 0)

    # Update Average Redirection Time
    alpha = 0.1  # Smoothing factor, adjust as needed
    updates["$set"]["average_redirection_time"] = round(
        (1 - alpha) * curr_avg + alpha * redirection_time, 2
    )

    if is_emoji:
        update_emoji_url(short_code, updates)
    else:
        update_url(short_code, updates)

    return redirect(url)


@url_redirector.route("/<short_code>/password", methods=["POST"])
@limiter.exempt
def check_password(short_code):
    projection = {
        "_id": 1,
        "password": 1,
    }

    short_code = unquote(short_code)
    if validate_emoji_alias(short_code):
        url_data = load_emoji_url(short_code, projection)
    else:
        url_data = load_url(short_code, projection)

    if url_data:
        # check if the URL is password protected
        if "password" in url_data:
            password = request.form.get("password")
            if password == url_data["password"]:
                return redirect(f"{request.host_url}{short_code}?password={password}")
            else:
                # show error message for incorrect password
                return render_template(
                    "password.html",
                    short_code=short_code,
                    error="Incorrect password",
                    host_url=request.host_url,
                )
    # show error message for invalid short code
    return (
        render_template(
            "error.html",
            error_code="400",
            error_message="Invalid short code or URL not password-protected",
            host_url=request.host_url,
        ),
        400,
    )
