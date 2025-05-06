import time
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    make_response,
)
from utils.url_utils import (
    BOT_USER_AGENTS,
    get_country,
    get_client_ip,
    validate_password,
    validate_url,
    validate_alias,
    validate_emoji_alias,
    validate_expiration_time,
    generate_short_code,
    generate_emoji_alias,
    convert_to_gmt,
)
from utils.mongo_utils import (
    load_url,
    update_url,
    insert_url,
    load_emoji_url,
    update_emoji_url,
    insert_emoji_url,
    check_if_slug_exists,
    check_if_emoji_alias_exists,
    validate_blocked_url,
    urls_collection,
)
from utils.general import is_positive_integer, humanize_number
from .limiter import limiter
from .cache import cache

from user_agents import parse
import json
from datetime import datetime, timezone
from urllib.parse import unquote
import re
import tldextract
from crawlerdetect import CrawlerDetect

url_shortener = Blueprint("url_shortener", __name__)

crawler_detect = CrawlerDetect()
tld_no_cache_extract = tldextract.TLDExtract(cache_dir=None)


@url_shortener.route("/", methods=["GET"])
@limiter.exempt
def index():
    recent_urls = []
    short_url_cookie = request.cookies.get("shortURL")
    if short_url_cookie:
        recent_urls = json.loads(short_url_cookie)
    return render_template(
        "index.html", host_url=request.host_url, recentURLs=recent_urls
    )


@url_shortener.route("/", methods=["POST"])
def shorten_url():
    url = request.values.get("url")
    password = request.values.get("password")
    max_clicks = request.values.get("max-clicks")
    alias = request.values.get("alias")
    expiration_time = request.values.get("expiration-time")
    block_bots = request.values.get("block-bots")

    if not url:
        if request.headers.get("Accept") == "application/json":
            return jsonify({"UrlError": "URL is required"}), 400
        else:
            return (
                render_template(
                    "index.html",
                    error="URL is required",
                    host_url=request.host_url,
                ),
                400,
            )

    if url and not validate_url(url):
        return (
            jsonify(
                {
                    "UrlError": "Invalid URL, URL must have a valid protocol and must follow rfc_1034 & rfc_2728 patterns"
                }
            ),
            400,
        )

    if url and not validate_blocked_url(url):
        return jsonify({"BlockedUrlError": "Blocked URL ⛔"}), 403

    if alias and not validate_alias(alias):
        if request.headers.get("Accept") == "application/json":
            return jsonify({"AliasError": "Invalid Alias", "alias": f"{alias}"}), 400
        else:
            return (
                render_template(
                    "index.html",
                    error="Invalid Alias",
                    url=url,
                    host_url=request.host_url,
                ),
                400,
            )

    elif alias:
        short_code = alias[:11]

    if alias and check_if_slug_exists(alias[:11]):
        if request.headers.get("Accept") == "application/json":
            return (
                jsonify({"AliasError": "Alias already exists", "alias": f"{alias}"}),
                400,
            )
        else:
            return (
                render_template(
                    "index.html",
                    error="Alias already exists",
                    url=url,
                    host_url=request.host_url,
                ),
                400,
            )
    elif alias:
        short_code = alias[:11]
    else:
        while True:
            short_code = generate_short_code()

            if not check_if_slug_exists(short_code):
                break

    if password:
        if not validate_password(password):
            return (
                jsonify(
                    {
                        "PasswordError": "Invalid password, password must be atleast 8 characters long, must contain a letter and a number and a special character either '@' or '.' and cannot be consecutive"
                    }
                ),
                400,
            )

        data = {
            "url": url,
            "password": password,
            "counter": {},
            "total-clicks": 0,
            "ips": [],
        }
    else:
        data = {"url": url, "counter": {}, "total-clicks": 0, "ips": []}

    if max_clicks:
        if not is_positive_integer(max_clicks):
            return (
                jsonify({"MaxClicksError": "max-clicks must be an positive integer"}),
                400,
            )
        else:
            max_clicks = str(abs(int(str(max_clicks))))
        data["max-clicks"] = max_clicks

    # custom expiration time is currently really buggy and not ready for production

    if expiration_time:
        if not validate_expiration_time(expiration_time):
            return (
                jsonify(
                    {
                        "ExpirationTimeError": "Invalid expiration-time. It must be in a valid ISO format with timezone information and at least 5 minutes from the current time."
                    }
                ),
                400,
            )
        else:
            data["expiration-time"] = expiration_time

    if block_bots:
        data["block-bots"] = True

    data["creation-date"] = datetime.now().strftime("%Y-%m-%d")
    data["creation-time"] = datetime.now().strftime("%H:%M:%S")

    data["creation-ip-address"] = get_client_ip()

    insert_url(short_code, data)

    response = jsonify({"short_url": f"{request.host_url}{short_code}"})

    if request.headers.get("Accept") == "application/json":
        return response
    else:
        serialized_list = request.cookies.get("shortURL")
        my_list = json.loads(serialized_list) if serialized_list else []
        my_list.insert(0, short_code)
        if len(my_list) > 3:
            del my_list[-1]
        serialized_list = json.dumps(my_list)
        resp = make_response(
            redirect(url_for("url_shortener.result", short_code=short_code))
        )
        resp.set_cookie("shortURL", serialized_list)

        return resp

    return response


@url_shortener.route("/emoji", methods=["GET", "POST"])
def emoji():
    emojies = request.values.get("emojies", None)
    url = request.values.get("url")
    password = request.values.get("password")
    max_clicks = request.values.get("max-clicks")
    expiration_time = request.values.get("expiration-time")
    block_bots = request.values.get("block-bots")

    if not url:
        return jsonify({"UrlError": "URL is required"}), 400

    if emojies:
        # emojies = unquote(emojies)
        if not validate_emoji_alias(emojies):
            return jsonify({"EmojiError": "Invalid emoji"}), 400

        if check_if_emoji_alias_exists(emojies):
            return jsonify({"EmojiError": "Emoji already exists"}), 400
    else:
        while True:
            emojies = generate_emoji_alias()

            if not check_if_emoji_alias_exists(emojies):
                break

    if url and not validate_url(url):
        return (
            jsonify(
                {
                    "UrlError": "Invalid URL, URL must have a valid protocol and must follow rfc_1034 & rfc_2728 patterns"
                }
            ),
            400,
        )

    if url and not validate_blocked_url(url):
        return jsonify({"UrlError": "Blocked URL ⛔"}), 403

    data = {"url": url, "counter": {}, "total-clicks": 0}

    if password:
        if not validate_password(password):
            return (
                jsonify(
                    {
                        "PasswordError": "Invalid password, password must be atleast 8 characters long, must contain a letter and a number and a special character either '@' or '.' and cannot be consecutive"
                    }
                ),
                400,
            )
        data["password"] = password

    if max_clicks:
        if not is_positive_integer(max_clicks):
            return (
                jsonify({"MaxClicksError": "max-clicks must be an positive integer"}),
                400,
            )
        else:
            max_clicks = str(abs(int(str(max_clicks))))
        data["max-clicks"] = max_clicks

    # custom expiration time is currently really buggy and not ready for production

    if expiration_time:
        if not validate_expiration_time(expiration_time):
            return (
                jsonify(
                    {
                        "ExpirationTimeError": "Invalid expiration-time. It must be in a valid ISO format with timezone information and at least 5 minutes from the current time."
                    }
                ),
                400,
            )
        else:
            data["expiration-time"] = expiration_time

    if block_bots:
        data["block-bots"] = True

    data["creation-date"] = datetime.now().strftime("%Y-%m-%d")
    data["creation-time"] = datetime.now().strftime("%H:%M:%S")

    data["creation-ip-address"] = get_client_ip()

    insert_emoji_url(emojies, data)

    response = jsonify({"short_url": f"{request.host_url}{emojies}"})

    if request.headers.get("Accept") == "application/json":
        return response

    return redirect(url_for("url_shortener.result", short_code=emojies))


@url_shortener.route("/result/<short_code>", methods=["GET"])
@limiter.exempt
def result(short_code):
    short_code = unquote(short_code)
    if validate_emoji_alias(short_code):
        url_data = load_emoji_url(short_code)
    else:
        url_data = load_url(short_code)

    if url_data:
        short_code = url_data["_id"]
        short_url = f"{request.host_url}{short_code}"
        return render_template(
            "result.html",
            short_url=short_url,
            short_code=short_code,
            host_url=request.host_url,
        )
    else:
        return (
            render_template(
                "error.html",
                error_code="404",
                error_message="URL NOT FOUND",
                host_url=request.host_url,
            ),
            404,
        )


@url_shortener.route("/<short_code>", methods=["GET"])
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

    if validate_emoji_alias(short_code):
        is_emoji = True
        url_data = load_emoji_url(short_code, projection)
    else:
        url_data = load_url(short_code, projection)

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

    # custom expiration time is currently really buggy and not ready for production

    if "expiration-time" in url_data:
        expiration_time = convert_to_gmt(url_data["expiration-time"])
        if not expiration_time:
            print("Expiration time is not timezone aware")
        elif expiration_time <= datetime.now(timezone.utc):
            return (
                render_template(
                    "error.html",
                    error_code="400",
                    error_message="SHORT CODE EXPIRED",
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

    try:
        ua = parse(user_agent)
    except TypeError:
        return "Invalid User-Agent", 400

    os_name = ua.os.family
    browser = ua.browser.family
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


@url_shortener.route("/<short_code>/password", methods=["POST"])
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


METRIC_PIPELINE = [
    {
        "$group": {
            "_id": None,
            "total-shortlinks": {"$sum": 1},
            "total-clicks": {"$sum": "$total-clicks"},
        }
    }
]


@url_shortener.route("/metric")
@limiter.exempt
@cache.cached(timeout=60)
def metric():
    result = urls_collection.aggregate(METRIC_PIPELINE).next()
    del result["_id"]
    result["total-clicks-raw"] = result["total-clicks"]
    result["total-shortlinks-raw"] = result["total-shortlinks"]
    result["total-clicks"] = humanize_number(result["total-clicks"])
    result["total-shortlinks"] = humanize_number(result["total-shortlinks"])
    return jsonify(result)
