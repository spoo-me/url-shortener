from flask import Blueprint
from utils import *
from .limiter import limiter

stats = Blueprint("stats", __name__)


@stats.route("/stats", methods=["GET", "POST"])
@limiter.exempt
def stats_route():
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


@stats.route("/stats/", methods=["GET", "POST"])
def stats_redirect():
    return redirect(url_for("stats.stats_route"))


@stats.route("/stats/<short_code>", methods=["GET", "POST"])
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

    if url_data.get("max-clicks") is not None:
        url_data["expired"] = url_data["total-clicks"] >= int(url_data["max-clicks"])
    else:
        url_data["expired"] = None

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
    url_data["bots"] = url_data.get("bots", {})

    url_data["referrer"] = url_data.get("referrer", {})
    url_data["country"] = url_data.get("country", {})
    url_data["browser"] = url_data.get("browser", {})
    url_data["os_name"] = url_data.get("os_name", {})
    url_data["ips"] = url_data.get("ips", {})

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

    except Exception as e:
        pass

    if "ips" in url_data:
        del url_data["ips"]
    if "creation-ip-address" in url_data:
        del url_data["creation-ip-address"]

    if url_data["counter"] != {}:
            url_data = add_missing_dates("counter", url_data)
    if "unique_counter" in url_data and url_data["unique_counter"] != {}:
        url_data = add_missing_dates("unique_counter", url_data)

    if request.method == "POST":
        return jsonify(url_data)
    else:
        try:
            url_data["hyper_link"] = url_data["url"]
            url_data["sorted_country"] = convert_country_data(url_data["country"])
            url_data["sorted_referrer"] = json.dumps(top_four(url_data["referrer"]))
            url_data["sorted_os_name"] = top_four(url_data["os_name"])
            url_data["sorted_browser"] = top_four(url_data["browser"])
            url_data["sorted_unique_browser"] = top_four(url_data["unique_browser"])
            url_data["sorted_unique_os_name"] = top_four(url_data["unique_os_name"])
            url_data["sorted_unique_country"] = convert_country_data(url_data["unique_country"])
            url_data["sorted_unique_referrer"] = json.dumps(
                top_four(url_data["unique_referrer"])
            )
            url_data["sorted_bots"] = top_four(url_data["bots"])
            url_data["analysis_data"] = {
                "average_daily_clicks": url_data["average_daily_clicks"],
                "average_weekly_clicks": url_data["average_weekly_clicks"],
                "average_monthly_clicks": url_data["average_monthly_clicks"],
            }
        except Exception as e:
            pass
        return render_template(
            "stats_view.html", json_data=url_data, host_url=request.host_url
        )


@stats.route("/export/<short_code>/<format>", methods=["GET", "POST"])
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
    url_data["bots"] = url_data.get("bots", {})

    url_data["referrer"] = url_data.get("referrer", {})
    url_data["country"] = url_data.get("country", {})
    url_data["browser"] = url_data.get("browser", {})
    url_data["os_name"] = url_data.get("os_name", {})
    url_data["ips"] = url_data.get("ips", {})

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

    except Exception as e:
        pass

    if "ips" in url_data:
        del url_data["ips"]
    if "creation-ip-address" in url_data:
        del url_data["creation-ip-address"]

    if url_data["counter"] != {}:
        url_data = add_missing_dates("counter", url_data)

    if "unique_counter" in url_data and url_data["unique_counter"] != {}:
        url_data = add_missing_dates("unique_counter", url_data)

    if format == "json":
        return export_to_json(url_data)
    elif format == "csv":
        return export_to_csv(url_data)
    elif format == "xlsx":
        return export_to_excel(url_data)
    elif format == "xml":
        return export_to_xml(url_data)
