from flask import Blueprint
from utils import *
from .limiter import limiter

from user_agents import parse
import tldextract

url_shortener = Blueprint("url_shortener", __name__)


@url_shortener.route("/", methods=["GET"])
@limiter.exempt
def index():
    serialized_list = request.cookies.get("shortURL")
    my_list = json.loads(serialized_list) if serialized_list else []
    if my_list:
        return render_template(
            "index.html", recentURLs=my_list, host_url=request.host_url
        )
    else:
        return render_template("index.html", host_url=request.host_url)


@url_shortener.route("/", methods=["POST"])
def shorten_url():
    url = request.values.get("url")
    password = request.values.get("password")
    max_clicks = request.values.get("max-clicks")
    alias = request.values.get("alias")
    expiration_time = request.values.get("expiration-time")

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

    if alias and not validate_string(alias):
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

        data = {"url": url, "password": password, "counter": {}, "total-clicks": 0}
    else:
        data = {"url": url, "counter": {}, "total-clicks": 0}

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

    data["creation-date"] = datetime.now().strftime("%Y-%m-%d")
    data["creation-time"] = datetime.now().strftime("%H:%M:%S")

    data["creation-ip-address"] = get_client_ip()

    add_url_by_id(short_code, data)

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
        resp = make_response(redirect(url_for("url_shortener.result", short_code=short_code)))
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

    data["creation-date"] = datetime.now().strftime("%Y-%m-%d")
    data["creation-time"] = datetime.now().strftime("%H:%M:%S")

    data["creation-ip-address"] = get_client_ip()

    add_emoji_by_alias(emojies, data)

    response = jsonify({"short_url": f"{request.host_url}{emojies}"})

    if request.headers.get("Accept") == "application/json":
        return response

    return redirect(url_for("url_shortener.result", short_code=emojies))


@url_shortener.route("/result/<short_code>", methods=["GET"])
@limiter.exempt
def result(short_code):

    short_code = unquote(short_code)
    if validate_emoji_alias(short_code):
        url_data = load_emoji_by_alias(short_code)
    else:
        url_data = load_url_by_id(short_code)

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

    short_code = unquote(short_code)
    if validate_emoji_alias(short_code):
        url_data = load_emoji_by_alias(short_code)
    else:
        url_data = load_url_by_id(short_code)

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
                    error_message="SHORT CODE EXPIRED",
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
            return render_template(
                "password.html", short_code=short_code, host_url=request.host_url
            )

    # store the device and browser information
    user_agent = request.headers.get("User-Agent")
    ua = parse(user_agent)
    os_name = ua.os.family
    browser = ua.browser.family
    user_ip = get_client_ip()
    referrer = request.headers.get("Referer")
    country = get_country(user_ip)

    if "referrer" not in url_data:
        url_data["referrer"] = {}
    if referrer:
        referrer_raw = tldextract.extract(referrer)
        referrer = f"{referrer_raw.domain}.{referrer_raw.suffix}"
        url_data["referrer"][referrer] = url_data["referrer"].get(
            referrer, {"ips": [], "counts": 0}
        )
        if not user_ip in url_data["referrer"][referrer]["ips"]:
            url_data["referrer"][referrer]["ips"].append(user_ip)
        url_data["referrer"][referrer]["counts"] += 1

    if "country" not in url_data:
        url_data["country"] = {}
    url_data["country"][country] = url_data["country"].get(
        country, {"ips": [], "counts": 0}
    )

    if not user_ip in url_data["country"][country]["ips"]:
        url_data["country"][country]["ips"].append(user_ip)
    url_data["country"][country]["counts"] += 1

    if "ips" not in url_data:
        url_data["ips"] = {}

    if "browser" not in url_data:
        url_data["browser"] = {}

    url_data["browser"][browser] = url_data["browser"].get(
        browser, {"ips": [], "counts": 0}
    )
    if not user_ip in url_data["browser"][browser]["ips"]:
        url_data["browser"][browser]["ips"].append(user_ip)
    url_data["browser"][browser]["counts"] += 1

    if "os_name" not in url_data:
        url_data["os_name"] = {}

    url_data["os_name"][os_name] = url_data["os_name"].get(
        os_name, {"ips": [], "counts": 0}
    )
    if not user_ip in url_data["os_name"][os_name]["ips"]:
        url_data["os_name"][os_name]["ips"].append(user_ip)
    url_data["os_name"][os_name]["counts"] += 1

    for bot in BOT_USER_AGENTS:
        bot_re = re.compile(bot, re.IGNORECASE)
        if bot_re.search(user_agent):
            url_data.setdefault("bots", {})[bot] = url_data.get("bots", {}).get(bot, 0) + 1
            break

    # increment the counter for the short code
    today = str(datetime.today()).split()[0]
    if today in url_data["counter"]:
        url_data["counter"][today] += 1
    else:
        url_data["counter"][today] = 1

    if not user_ip in url_data["ips"]:
        if not "unique_counter" in url_data:
            url_data["unique_counter"] = {}
        if today in url_data["unique_counter"]:
            url_data["unique_counter"][today] += 1
        else:
            url_data["unique_counter"][today] = 1

    url_data["ips"][user_ip] = url_data["ips"].get(user_ip, 0) + 1

    url_data["total-clicks"] += 1
    url_data["last-click"] = str(
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    url_data["last-click-browser"] = browser
    url_data["last-click-os"] = os_name
    url_data["last-click-country"] = country

    if validate_emoji_alias(short_code):
        update_emoji_by_alias(short_code, url_data)
    else:
        update_url_by_id(short_code, url_data)

    return redirect(url)


@url_shortener.route("/<short_code>/password", methods=["POST"])
@limiter.exempt
def check_password(short_code):

    short_code = unquote(short_code)
    if validate_emoji_alias(short_code):
        url_data = load_emoji_by_alias(short_code)
    else:
        url_data = load_url_by_id(short_code)

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
