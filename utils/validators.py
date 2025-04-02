from functools import wraps
from flask import request, jsonify, render_template
from flask.typing import ResponseReturnValue
from utils.url_utils import (
    validate_url,
    validate_password,
    validate_alias,
    validate_emoji_alias,
)
from utils.mongo_utils import (
    alias_exists,
    emoji_exists,
    validate_blocked_url,
)
from utils.general import is_positive_integer


def error_response(
    error_key, message, status_code=400, template="index.html"
) -> ResponseReturnValue:
    """Returns error in json format or HTML format based on request headers"""
    if request.headers.get("Accept") == "application/json":
        return jsonify({error_key: message}), status_code
    return render_template(
        template, error=message, host_url=request.host_url
    ), status_code


def validate_alias_request(template="index.html"):
    """Decorator to validate the alias request"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            alias: str | None = request.values.get("alias")

            if not alias:
                return func(*args, **kwargs)

            # Alias Validation
            if not validate_alias(alias):
                return error_response("AliasError", "Invalid Alias", template=template)

            if alias_exists(alias[:11]):
                return error_response(
                    "AliasError", "Alias already exists", template=template
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_emoji_request(template="index.html"):
    """Decorator to validate the emoji request"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            emojies: str | None = request.values.get("emojies")

            if not emojies:
                return func(*args, **kwargs)

            # Emoji Validation
            if not validate_emoji_alias(emojies):
                return error_response("EmojiError", "Invalid Emoji", template=template)

            if emoji_exists(emojies):
                return error_response(
                    "EmojiError", "Emoji already exists", template=template
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_shorten_request(template="index.html"):
    """Decorator to validate the shorten URL request"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            url: str | None = request.values.get("url")
            password: str | None = request.values.get("password")
            max_clicks: str | None = request.values.get("max-clicks")

            # URL Validation
            if not url:
                return error_response("UrlError", "URL is required", 400, template)

            if not validate_url(url):
                return error_response(
                    "UrlError",
                    "Invalid URL, URL must have a valid protocol and must follow rfc_1034 & rfc_2728 patterns",
                    400,
                    template,
                )

            if not validate_blocked_url(url):
                return error_response(
                    "BlockedUrlError", "Blocked URL ⛔", 403, template
                )

            # Password Validation
            if password and not validate_password(password):
                return error_response(
                    "PasswordError",
                    "Invalid password, password must be atleast 8 characters long, must contain a letter and a number and a special character either '@' or '.' and cannot be consecutive",
                    400,
                    template,
                )

            # Max Clicks Validation
            if max_clicks and not is_positive_integer(max_clicks):
                return error_response(
                    "MaxClicksError",
                    "max-clicks must be an positive integer",
                    400,
                    template,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator
