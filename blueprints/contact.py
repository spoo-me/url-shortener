from flask import Blueprint
from utils import *
from .limiter import limiter

contact = Blueprint("contact", __name__)


@contact.route("/contact", methods=["GET", "POST"])
@limiter.limit("20/day")
@limiter.limit("10/hour")
@limiter.limit("3/minute")
def contact_route():
    if request.method == "POST":
        email = request.values.get("email")
        message = request.values.get("message")
        hcaptcha_token = request.values.get("h-captcha-response")

        if not hcaptcha_token:
            return (
                render_template(
                    "contact.html",
                    error="Please complete the captcha",
                    host_url=request.host_url,
                    email=email,
                    message=message
                ),
                400,
            )

        if not verify_hcaptcha(hcaptcha_token):
            return (
                render_template(
                    "contact.html",
                    error="Invalid captcha, please try again",
                    host_url=request.host_url,
                    email=email,
                    message=message
                ),
                400,
            )

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
            send_contact_message(CONTACT_WEBHOOK, email, message)
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


@contact.route("/report", methods=["GET", "POST"])
@limiter.limit("20/day")
@limiter.limit("10/hour")
@limiter.limit("3/minute")
def report():
    if request.method == "POST":
        short_code = request.values.get("short_code")
        reason = request.values.get("reason")
        hcaptcha_token = request.values.get("h-captcha-response")

        if not hcaptcha_token:
            return (
                render_template(
                    "report.html",
                    error="Please complete the captcha",
                    host_url=request.host_url,
                    short_code=short_code,
                    reason=reason
                ),
                400,
            )

        if not verify_hcaptcha(hcaptcha_token):
            return (
                render_template(
                    "report.html",
                    error="Invalid captcha, please try again",
                    host_url=request.host_url,
                    short_code=short_code,
                    reason=reason
                ),
                400,
            )

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
            send_report(
                URL_REPORT_WEBHOOK,
                short_code,
                reason,
                request.remote_addr,
                request.host_url,
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
