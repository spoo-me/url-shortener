from flask import Blueprint, render_template, request
from utils.contact_utils import (
    send_contact_message,
    verify_hcaptcha,
    send_report,
    CONTACT_WEBHOOK,
    URL_REPORT_WEBHOOK,
)
from utils.mongo_utils import check_if_slug_exists, check_if_v2_alias_exists
from utils.url_utils import get_client_ip
from utils.logger import get_logger
from .limiter import limiter

contact = Blueprint("contact", __name__)
log = get_logger(__name__)


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
                    message=message,
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
                    message=message,
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
            log.info(
                "contact_message_sent",
                email_domain=email.split("@")[1] if "@" in email else "unknown",
                message_length=len(message),
            )
        except Exception as e:
            log.error(
                "webhook_send_failed",
                webhook_type="contact",
                error=str(e),
                error_type=type(e).__name__,
            )
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
        # Only read from form data (POST), not query parameters
        short_code = request.form.get("short_code")
        reason = request.form.get("reason")
        hcaptcha_token = request.form.get("h-captcha-response")

        if not hcaptcha_token:
            return (
                render_template(
                    "report.html",
                    error="Please complete the captcha",
                    host_url=request.host_url,
                    short_code=short_code,
                    reason=reason,
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
                    reason=reason,
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

        # Check both v1 (urls) and v2 (urlsV2) collections
        url_exists = check_if_slug_exists(short_code) or check_if_v2_alias_exists(
            short_code
        )

        if not url_exists:
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
                get_client_ip(),
                request.host_url,
            )
            log.info(
                "url_report_sent",
                short_code=short_code,
                reason=reason[:50],  # Truncate reason for logging
            )
        except Exception as e:
            log.error(
                "webhook_send_failed",
                webhook_type="report",
                short_code=short_code,
                error=str(e),
                error_type=type(e).__name__,
            )
            return render_template(
                "report.html",
                error="Error sending report, please try again later",
                host_url=request.host_url,
            )
        return render_template(
            "report.html", success="Report sent successfully", host_url=request.host_url
        )
    return render_template("report.html", host_url=request.host_url)
