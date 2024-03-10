from flask import (
    Flask,
    jsonify,
    request,
    redirect,
    render_template,
    url_for,
    send_file,
    make_response,
)
import json
from datetime import datetime, timezone, timedelta
from user_agents import parse
import geoip2.database
import tldextract
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import atexit
from utils import *

app = Flask(__name__)
CORS(app)
limiter = Limiter(
    get_remote_address,
    app=app,
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

    return request.remote_addr in bypasses


@app.route("/", methods=["GET"])
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


@app.route("/", methods=["POST"])
def shorten_url():
    url = request.values.get("url")
    password = request.values.get("password")
    max_clicks = request.values.get("max-clicks")
    alias = request.values.get("alias")
    expiration_time = request.values.get("expiration-time")

    app.logger.info(f"Received request data: {request.values}")

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
        resp = make_response(redirect(url_for("result", short_code=short_code)))
        resp.set_cookie("shortURL", serialized_list)

        return resp

    return response


@app.route("/emoji", methods=["GET", "POST"])
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

    return redirect(url_for("result", short_code=emojies))


@app.route("/result/<short_code>", methods=["GET"])
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


def get_country(ip_address):
    reader = geoip2.database.Reader("misc/GeoLite2-Country.mmdb")
    try:
        response = reader.country(ip_address)
        country = response.country.name
        return country
    except geoip2.errors.AddressNotFoundError:
        return "Unknown"
    finally:
        reader.close()


def get_client_ip():
    if "HTTP_X_FORWARDED_FOR" in request.environ:
        # If the request is proxied, retrieve the IP address from the X-Forwarded-For header
        ip_list = request.environ["HTTP_X_FORWARDED_FOR"].split(",")
        # The client's IP address is typically the first entry in the list
        return ip_list[0].strip()
    else:
        # If the request is not proxied, use the remote address
        return request.environ.get("REMOTE_ADDR", "")


@app.route("/<short_code>", methods=["GET"])
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


@app.route("/<short_code>/password", methods=["POST"])
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


@app.route("/stats", methods=["GET", "POST"])
@limiter.exempt
def stats():
    if request.method == "POST":
        short_code = request.values.get("short_code")
        short_code = short_code[short_code.rfind("/") + 1 :]
        password = request.values.get("password")

        short_code = unquote(short_code)

        if validate_emoji_alias(short_code):
            url_data = load_emoji_by_alias(short_code)
        else:
            url_data = load_url_by_id(short_code)

        if not url_data:
            return render_template(
                "stats.html",
                error="Invalid Short Code, short code does not exist!",
                url=short_code,
                host_url=request.host_url,
            )

        if not password and "password" in url_data:
            return render_template(
                "stats.html",
                password_error=f"{request.host_url}{short_code} is a password protected Url, please enter the password to continue.",
                url=short_code,
                host_url=request.host_url,
            )

        if "password" in url_data and url_data["password"] != password:
            return render_template(
                "stats.html",
                password_error="Invalid Password! please enter the correct password to continue.",
                url=short_code,
                host_url=request.host_url,
            )

        if "password" in url_data:
            return redirect(f"/stats/{short_code}?password={password}")
        else:
            return redirect(f"/stats/{short_code}")

    return render_template("stats.html", host_url=request.host_url)


@app.route("/stats/", methods=["GET", "POST"])
def stats_redirect():
    return redirect(url_for("stats"))


@app.route("/stats/<short_code>", methods=["GET", "POST"])
@limiter.exempt
def analytics(short_code):
    password = request.values.get("password")

    short_code = unquote(short_code)

    if validate_emoji_alias(short_code):
        url_data = load_emoji_by_alias(short_code)
    else:
        url_data = load_url_by_id(short_code)

    if not url_data:
        if request.method == "GET":
            return (
                render_template(
                    "error.html",
                    error_code="404",
                    error_message="URL NOT FOUND",
                    host_url=request.host_url,
                ),
                404,
            )
        else:
            return jsonify({"UrlError": "The requested Url never existed"}), 404

    if "password" in url_data:
        if password != url_data["password"]:
            if request.method == "POST":
                return (
                    jsonify(
                        {"PasswordError": "Invalid Password", "entered-pass": password}
                    ),
                    400,
                )
            else:
                return (
                    render_template(
                        "stats.html",
                        url=short_code,
                        password_error=f"{request.host_url}{short_code} is a password protected Url, please enter the password to continue.",
                        host_url=request.host_url,
                    ),
                    400,
                )

    url_data["expired"] = False

    if "max-clicks" in url_data:
        if url_data["total-clicks"] >= int(url_data["max-clicks"]):
            url_data["expired"] = True

    if "expiration-time" in url_data:
        expiration_time = convert_to_gmt(url_data["expiration-time"])
        if not expiration_time:
            print("Expiration time is not timezone aware")
        elif expiration_time <= datetime.now(timezone.utc):
            url_data["expired"] = True

    url_data["max-clicks"] = url_data.get("max-clicks", None)
    url_data["expiration-time"] = url_data.get("expiration-time", None)
    url_data["password"] = url_data.get("password", None)

    url_data["short_code"] = short_code
    url_data["last-click-browser"] = url_data.get("last-click-browser", None)
    url_data["last-click-os"] = url_data.get("last-click-os", None)

    try:
        url_data["unique_referrer"] = {}
        url_data["unique_country"] = {}
        url_data["unique_browser"] = {}
        url_data["unique_os_name"] = {}

        for i in url_data["referrer"]:
            if len(url_data["referrer"][i]["ips"]) != 0:
                url_data["unique_referrer"][i] = len(url_data["referrer"][i]["ips"])
            url_data["referrer"][i] = url_data["referrer"][i]["counts"]
        for i in url_data["country"]:
            if len(url_data["country"][i]["ips"]) != 0:
                url_data["unique_country"][i] = len(url_data["country"][i]["ips"])
            url_data["country"][i] = url_data["country"][i]["counts"]
        for i in url_data["browser"]:
            if len(url_data["browser"][i]["ips"]) != 0:
                url_data["unique_browser"][i] = len(url_data["browser"][i]["ips"])
            url_data["browser"][i] = url_data["browser"][i]["counts"]
        for i in url_data["os_name"]:
            if len(url_data["os_name"][i]["ips"]) != 0:
                url_data["unique_os_name"][i] = len(url_data["os_name"][i]["ips"])
            url_data["os_name"][i] = url_data["os_name"][i]["counts"]

        url_data["total_unique_clicks"] = len(url_data["ips"].keys())
        (
            url_data["average_daily_clicks"],
            url_data["average_weekly_clicks"],
            url_data["average_monthly_clicks"],
        ) = calculate_click_averages(url_data)

        if "ips" in url_data:
            del url_data["ips"]
        if "creation-ip-address" in url_data:
            del url_data["creation-ip-address"]
    except:
        if "browser" and "os_name" in url_data:
            url_data["unique_browser"] = {}
            url_data["unique_os_name"] = {}

            for i in url_data["browser"]:
                url_data["unique_browser"][i] = len(url_data["browser"][i]["ips"])
                url_data["browser"][i] = url_data["browser"][i]["counts"]
            for i in url_data["os_name"]:
                url_data["unique_os_name"][i] = len(url_data["os_name"][i]["ips"])
                url_data["os_name"][i] = url_data["os_name"][i]["counts"]

        if "ips" in url_data:
            del url_data["ips"]
        if "creation-ip-address" in url_data:
            del url_data["creation-ip-address"]

    if request.method == "POST":
        if url_data["counter"] != {}:
            url_data = add_missing_dates("counter", url_data)
        try:
            if url_data["unique_counter"] != {}:
                url_data = add_missing_dates("unique_counter", url_data)
        except:
            pass
        return jsonify(url_data)

    else:
        if url_data["counter"] != {}:
            url_data = add_missing_dates("counter", url_data)

        try:
            url_data["hyper_link"] = url_data["url"]
            if url_data["unique_counter"] != {}:
                url_data = add_missing_dates("unique_counter", url_data)
            url_data["sorted_country"] = top_four(url_data["country"])
            url_data["sorted_referrer"] = json.dumps(top_four(url_data["referrer"]))
            url_data["sorted_os_name"] = top_four(url_data["os_name"])
            url_data["sorted_browser"] = top_four(url_data["browser"])
            url_data["sorted_unique_browser"] = top_four(url_data["unique_browser"])
            url_data["sorted_unique_os_name"] = top_four(url_data["unique_os_name"])
            url_data["sorted_unique_country"] = top_four(url_data["unique_country"])
            url_data["sorted_unique_referrer"] = json.dumps(
                top_four(url_data["unique_referrer"])
            )
            url_data["analysis_data"] = {
                "average_daily_clicks": url_data["average_daily_clicks"],
                "average_weekly_clicks": url_data["average_weekly_clicks"],
                "average_monthly_clicks": url_data["average_monthly_clicks"],
            }
        except:
            pass
        return render_template(
            "stats_view.html", json_data=url_data, host_url=request.host_url
        )


@app.route("/export/<short_code>/<format>", methods=["GET", "POST"])
@limiter.exempt
def export(short_code, format):
    format = format.lower()
    password = request.values.get("password")
    short_code = unquote(short_code)

    if format not in ["csv", "json", "xlsx", "xml"]:
        if request.method == "GET":
            return (
                render_template(
                    "error.html",
                    error_code="400",
                    error_message="Invalid format, format must be json, csv, xml or xlsx",
                    host_url=request.host_url,
                ),
                400,
            )
        else:
            return (
                jsonify(
                    {
                        "FormatError": "Invalid format; format must be json, csv, xlsx or xml"
                    }
                ),
                400,
            )

    if validate_emoji_alias(short_code):
        url_data = load_emoji_by_alias(short_code)
    else:
        url_data = load_url_by_id(short_code)

    if not url_data:
        if request.method == "GET":
            return (
                render_template(
                    "error.html",
                    error_code="404",
                    error_message="URL NOT FOUND",
                    host_url=request.host_url,
                ),
                404,
            )
        else:
            return jsonify({"UrlError": "The requested Url never existed"}), 404

    if "password" in url_data:
        if password != url_data["password"]:
            if request.method == "POST":
                return (
                    jsonify(
                        {"PasswordError": "Invalid Password", "entered-pass": password}
                    ),
                    400,
                )
            else:
                return (
                    render_template(
                        "error.html",
                        error_code="400",
                        error_message="Invalid Password",
                        host_url=request.host_url,
                    ),
                    400,
                )

    url_data["short_code"] = short_code

    if url_data.get("max-clicks") is not None:
        url_data["expired"] = url_data["total-clicks"] >= int(url_data["max-clicks"])
    else:
        url_data["expired"] = None

    if url_data.get("expiration-time") is not None:
        expiration_time = convert_to_gmt(url_data["expiration-time"])
        if not expiration_time:
            print("Expiration time is not timezone aware")
        elif expiration_time <= datetime.now(timezone.utc):
            url_data["expired"] = True

    url_data["max-clicks"] = url_data.get("max-clicks")
    url_data["expiration-time"] = url_data.get("expiration-time")
    url_data["password"] = url_data.get("password")
    url_data["last-click-browser"] = url_data.get("last-click-browser")
    url_data["last-click-os"] = url_data.get("last-click-os")

    try:
        url_data["unique_referrer"] = {}
        url_data["unique_country"] = {}
        url_data["unique_browser"] = {}
        url_data["unique_os_name"] = {}

        for i in url_data["referrer"]:
            if len(url_data["referrer"][i]["ips"]) != 0:
                url_data["unique_referrer"][i] = len(url_data["referrer"][i]["ips"])
            url_data["referrer"][i] = url_data["referrer"][i]["counts"]
        for i in url_data["country"]:
            if len(url_data["country"][i]["ips"]) != 0:
                url_data["unique_country"][i] = len(url_data["country"][i]["ips"])
            url_data["country"][i] = url_data["country"][i]["counts"]
        for i in url_data["browser"]:
            if len(url_data["browser"][i]["ips"]) != 0:
                url_data["unique_browser"][i] = len(url_data["browser"][i]["ips"])
            url_data["browser"][i] = url_data["browser"][i]["counts"]
        for i in url_data["os_name"]:
            if len(url_data["os_name"][i]["ips"]) != 0:
                url_data["unique_os_name"][i] = len(url_data["os_name"][i]["ips"])
            url_data["os_name"][i] = url_data["os_name"][i]["counts"]

        url_data["total_unique_clicks"] = len(url_data["ips"].keys())
        (
            url_data["average_daily_clicks"],
            url_data["average_weekly_clicks"],
            url_data["average_monthly_clicks"],
        ) = calculate_click_averages(url_data)

    except:
        if "browser" and "os_name" in url_data:
            url_data["unique_browser"] = {}
            url_data["unique_os_name"] = {}

            for i in url_data["browser"]:
                url_data["unique_browser"][i] = len(url_data["browser"][i]["ips"])
                url_data["browser"][i] = url_data["browser"][i]["counts"]
            for i in url_data["os_name"]:
                url_data["unique_os_name"][i] = len(url_data["os_name"][i]["ips"])
                url_data["os_name"][i] = url_data["os_name"][i]["counts"]

    if "ips" in url_data:
        del url_data["ips"]
    if "creation-ip-address" in url_data:
        del url_data["creation-ip-address"]

    if url_data["counter"] != {}:
        url_data = add_missing_dates("counter", url_data)

    try:
        if url_data["unique_counter"] != {}:
            url_data = add_missing_dates("unique_counter", url_data)
    except:
        pass

    if format == "json":
        return export_to_json(url_data)
    elif format == "csv":
        return export_to_csv(url_data)
    elif format == "xlsx":
        return export_to_excel(url_data)
    elif format == "xml":
        return export_to_xml(url_data)


@app.route("/api", methods=["GET"])
@limiter.exempt
def api():
    return render_template("api.html", host_url=request.host_url)


@app.route("/contact", methods=["GET", "POST"])
@limiter.limit("20/day")
@limiter.limit("10/hour")
@limiter.limit("3/minute")
def contact():
    if request.method == "POST":
        email = request.values.get("email")
        message = request.values.get("message")
        if not email or not message:
            return (
                render_template(
                    "contact.html",
                    error="All fields are required",
                    host_url=request.host_url,
                ),
                400,
            )

        try:
            send_webhook(message=f"# `{email}`\n\n {message}", url=CONTACT_WEBHOOK)
        except Exception as e:
            print(f"Error sending webhook: {e}")
            return render_template(
                "contact.html",
                error="Error sending message, please try again later",
                host_url=request.host_url,
            )

        return render_template(
            "contact.html",
            success="Message sent successfully",
            host_url=request.host_url,
        )
    return render_template("contact.html", host_url=request.host_url)


@app.route("/report", methods=["GET", "POST"])
@limiter.limit("20/day")
@limiter.limit("10/hour")
@limiter.limit("3/minute")
def report():
    if request.method == "POST":
        short_code = request.values.get("short_code")
        reason = request.values.get("reason")
        if not short_code or not reason:
            return (
                render_template(
                    "report.html",
                    error="All fields are required",
                    host_url=request.host_url,
                ),
                400,
            )

        short_code = short_code.split("/")[-1]
        if not check_if_slug_exists(short_code):
            return (
                render_template(
                    "report.html",
                    error="Invalid short code, short code does not exist",
                    host_url=request.host_url,
                ),
                400,
            )

        try:
            send_webhook(
                message=f"# Short Code: `{short_code}`\nReason: {reason}",
                url=URL_REPORT_WEBHOOK,
            )
        except Exception as e:
            print(f"Error sending webhook: {e}")
            return render_template(
                "report.html",
                error="Error sending report, please try again later",
                host_url=request.host_url,
            )
        return render_template(
            "report.html", success="Report sent successfully", host_url=request.host_url
        )
    return render_template("report.html", host_url=request.host_url)


@app.route("/docs/<file_name>")
@limiter.exempt
def serve_docs(file_name):
    try:
        ext = file_name.split(".")[1]
        if ext in ["html"]:
            return render_template(f"docs/{file_name}", host_url=request.host_url)
        else:
            return send_file(f"docs/{file_name}")
    except:
        return (
            render_template(
                "error.html",
                error_code="404",
                error_message="URL NOT FOUND",
                host_url=request.host_url,
            ),
            404,
        )


@app.route("/legal/privacy-policy")
@limiter.exempt
def serve_privacy_policy():
    return render_template("docs/privacy-policy.html", host_url=request.host_url)


@app.route("/sitemap.xml")
@limiter.exempt
def serve_sitemap():
    return send_file("misc/sitemap.xml")


@app.route("/security.txt")
@limiter.exempt
def serve_security():
    return send_file("misc/security.txt")


@app.route("/humans.txt")
@limiter.exempt
def serve_humans():
    return send_file("misc/humans.txt")


@app.route("/robots.txt")
@limiter.exempt
def serve_robots():
    return send_file("misc/robots.txt")


@app.errorhandler(404)
def page_not_found(error):
    return (
        render_template(
            "error.html",
            error_code="404",
            error_message="URL NOT FOUND!",
            host_url=request.host_url,
        ),
        404,
    )


@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path == "/contact":
        return render_template(
            "contact.html",
            error=f"ratelimit exceeded {e.description}",
            host_url=request.host_url,
        )
    if request.path == "/report":
        return render_template(
            "report.html",
            error=f"ratelimit exceeded {e.description}",
            host_url=request.host_url,
        )
    return make_response(jsonify(error=f"ratelimit exceeded {e.description}"), 429)


@atexit.register
def cleanup():
    try:
        client.close()
        print("MongoDB connection closed successfully")
    except Exception as e:
        print(f"Error closing MongoDB connection: {e}")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000, use_reloader=False)
