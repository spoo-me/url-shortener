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
    default_limits=["3 per minute", "75 per day", "20 per hour"],
    storage_uri=MONGO_URI,
    strategy="fixed-window",
)


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

    app.logger.info(f"Received request data: {request.values}")

    if not validate_url(url):
        return jsonify({"UrlError": "Invalid URL"}), 400

    if not validate_blocked_url(url):
        return jsonify({"UrlError": "Blocked URL ⛔"}), 403

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


@app.route("/result/<short_code>", methods=["GET"])
@limiter.exempt
def result(short_code):
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
        return render_template(
            "error.html",
            error_code="404",
            error_message="URL NOT FOUND",
            host_url=request.host_url,
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
    url_data = load_url_by_id(short_code)

    if not url_data:
        return render_template(
            "error.html",
            error_code="404",
            error_message="URL NOT FOUND",
            host_url=request.host_url,
        )

    url = url_data["url"]
    # check if the URL is password protected
    if not "password" in url_data:
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

    if "password" in url_data:
        # check if the user provided the password through the URL parameter
        password = request.args.get("password")
        if password == url_data["password"]:
            pass
        else:
            # prompt the user for the password
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

            return render_template(
                "password.html", short_code=short_code, host_url=request.host_url
            )

    # store the device and browser information
    user_agent = request.headers.get("User-Agent")
    ua = parse(user_agent)
    os_name = ua.os.family  # Get the operating system name
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

    update_url_by_id(short_code, url_data)

    return redirect(url)


@app.route("/<short_code>/password", methods=["POST"])
@limiter.exempt
def check_password(short_code):
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
        short_code = request.form["short_code"]
        short_code = short_code[short_code.rfind("/") + 1 :]
        password = request.form["password"]

        url_data = load_url_by_id(short_code)

        if not url_data:
            return render_template(
                "stats.html",
                error="Invalid URL",
                url=short_code,
                host_url=request.host_url,
            )

        if not password and "password" in url_data:
            return render_template(
                "stats.html",
                error="Password Not Provided",
                url={{request.host_url}} + short_code,
                host_url=request.host_url,
            )

        if "password" in url_data and url_data["password"] != password:
            return render_template(
                "stats.html",
                error="Invalid Password!",
                url={{request.host_url}} + short_code,
                host_url=request.host_url,
            )

        if "password" in url_data:
            return redirect(f"/stats/{short_code}?password={password}")
        else:
            return redirect(f"/stats/{short_code}")

    return render_template("stats.html", host_url=request.host_url)


@app.route("/stats/<short_code>", methods=["GET", "POST"])
@limiter.exempt
def analytics(short_code):
    password = request.values.get("password")

    url_data = load_url_by_id(short_code)

    if not url_data:
        if request.method == "GET":
            return render_template(
                "error.html",
                error_code="404",
                error_message="URL NOT FOUND",
                host_url=request.host_url,
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
                return render_template(
                    "stats_error.html",
                    url=request.host_url + short_code,
                    geterror=f"{request.host_url}{short_code} is a password protected Url, please enter the password to view its stats.",
                    host_url=request.host_url,
                )

    if "max-clicks" in url_data:
        if url_data["total-clicks"] >= int(url_data["max-clicks"]):
            url_data["expired"] = True
        else:
            url_data["expired"] = False
    else:
        url_data["expired"] = None

    url_data["max-clicks"] = (
        None if "max-clicks" not in url_data else url_data["max-clicks"]
    )

    if "password" not in url_data:
        url_data["password"] = None

    url_data["short_code"] = short_code
    url_data["last-click-browser"] = (
        None if "last-click-browser" not in url_data else url_data["last-click-browser"]
    )
    url_data["last-click-os"] = (
        None if "last-click-os" not in url_data else url_data["last-click-os"]
    )

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

        try:
            del url_data["ips"]
            del url_data["creation-ip-address"]
        except:
            pass
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
        try:
            del url_data["ips"]
            del url_data["creation-ip-address"]
        except:
            pass

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


@app.route("/api", methods=["GET"])
@limiter.exempt
def api():
    return render_template("api.html", host_url=request.host_url)


@app.route("/sitemap.xml")
@limiter.exempt
def serve_sitemap():
    return send_file("misc/sitemap.xml")


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
    return make_response(jsonify(error=f"ratelimit exceeded {e.description}"), 429)


@atexit.register
def cleanup():
    try:
        client.close()
        print("MongoDB connection closed successfully")
    except Exception as e:
        print(f"Error closing MongoDB connection: {e}")


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
