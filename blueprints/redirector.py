from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
)
from utils.url_utils import (
    BOT_USER_AGENTS,
    get_client_ip,
    validate_emoji_alias,
)
from utils.mongo_utils import (
    load_url,
    load_emoji_url,
)
from cache import cache_query as cq
from cache.cache_url import UrlData

from .limiter import limiter

from ua_parser import parse
from datetime import datetime, timezone
from urllib.parse import unquote
import re
from crawlerdetect import CrawlerDetect

from workers.stats_publisher import send_to_queue

crawler_detect = CrawlerDetect()

url_redirector = Blueprint("url_redirector", __name__)


@url_redirector.route("/<short_code>", methods=["GET"])
@limiter.exempt
def redirect_url(short_code: str):
    user_ip = get_client_ip()
    projection = {
        "_id": 1,
        "url": 1,
        "password": 1,
        "max-clicks": 1,
        "total-clicks": 1,
        "ips": {"$elemMatch": {"$eq": user_ip}},
        "block-bots": 1,
        "average_redirection_time": 1,
    }

    short_code = unquote(short_code)
    is_emoji = validate_emoji_alias(short_code)

    cached_url_data = cq.get_url_data(short_code)
    if cached_url_data:
        url_data = {
            "url": cached_url_data.url,
            "password": cached_url_data.password,
            "block-bots": cached_url_data.block_bots,
        }
    else:
        if is_emoji:
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
        if not ua or not ua.string:
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

    os_name = ua.os.family if ua.os else "Unknown"
    browser = ua.user_agent.family if ua.user_agent else "Unknown"
    referrer = request.headers.get("Referer")

    is_unique_click = url_data.get("ips", None) is None
    bot_name: str | None = None

    for bot in BOT_USER_AGENTS:
        bot_re = re.compile(bot, re.IGNORECASE)
        if bot_re.search(user_agent):
            bot_name = bot
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
            break
    else:
        if crawler_detect.isCrawler(user_agent):
            bot_name = crawler_detect.getMatches()[0]
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

    message = {
        "short_code": short_code,
        "os_name": os_name,
        "browser": browser,
        "referrer": referrer,
        "ip": user_ip,
        "user_agent": user_agent,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "is_unique_click": is_unique_click,
        "bot_name": bot_name,
        "is_emoji": is_emoji,
    }

    # send the stats message to the stats queue to be processed later
    if request.method == "HEAD":
        pass
    else:
        send_to_queue(message)

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
