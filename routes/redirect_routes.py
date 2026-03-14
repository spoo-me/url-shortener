"""
Redirect routes — the hot path.

GET  /<short_code>          → resolve + redirect (rate-limit exempt)
POST /<short_code>/password → password form submission
"""

from __future__ import annotations

import os
import time
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from dependencies import get_click_service, get_url_service
from errors import ForbiddenError, GoneError, NotFoundError, ValidationError
from middleware.rate_limiter import limiter
from services.click import ClickService
from services.url_service import UrlService
from shared.crypto import verify_password
from shared.ip_utils import get_client_ip
from shared.logging import get_logger

log = get_logger(__name__)

router = APIRouter()

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


def _check_url_password(password: str | None, password_hash: str, schema: str) -> bool:
    """Verify a URL password — bcrypt for v2, plaintext comparison for v1/emoji."""
    if schema == "v2":
        return verify_password(password or "", password_hash)
    return password == password_hash


@router.api_route("/{short_code}", methods=["GET", "HEAD"])
@limiter.exempt
async def redirect_url(
    short_code: str,
    request: Request,
    url_service: UrlService = Depends(get_url_service),
    click_service: ClickService = Depends(get_click_service),
) -> Response:
    """Resolve a short code and redirect to the destination URL.

    Rate-limit exempt — this is the hot path (~400k requests/day).
    """
    short_code = unquote(short_code)
    user_ip = get_client_ip(request)
    start_time = time.perf_counter()
    host_url = str(request.base_url)

    # 1. Resolve URL (cache-first)
    try:
        url_data, schema = await url_service.resolve(short_code)
    except NotFoundError:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "error_code": "404",
                "error_message": "URL NOT FOUND",
                "host_url": host_url,
            },
            status_code=404,
        )
    except ForbiddenError:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "error_code": "403",
                "error_message": "ACCESS DENIED",
                "host_url": host_url,
            },
            status_code=403,
        )
    except GoneError:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "error_code": "410",
                "error_message": "SHORT URL EXPIRED",
                "host_url": host_url,
            },
            status_code=410,
        )

    # 2. Password check
    if url_data.password_hash:
        password = request.query_params.get("password")
        if not _check_url_password(password, url_data.password_hash, schema):
            return templates.TemplateResponse(
                request,
                "password.html",
                {"short_code": short_code, "host_url": host_url},
                status_code=401,
            )

    # 3. Track click — skip for HEAD / OPTIONS
    if request.method not in ("HEAD", "OPTIONS"):
        user_agent = request.headers.get("User-Agent", "")
        referrer = request.headers.get("Referer")
        cf_city = request.headers.get("CF-IPCity")
        is_emoji = schema == "emoji"
        try:
            await click_service.track_click(
                url_data=url_data,
                short_code=short_code,
                schema=schema,
                is_emoji=is_emoji,
                client_ip=user_ip,
                start_time=start_time,
                user_agent=user_agent,
                referrer=referrer,
                cf_city=cf_city,
            )
        except ValidationError:
            # Bad / missing User-Agent — skip analytics, still redirect
            log.warning(
                "click_tracking_validation_error", short_code=short_code, schema=schema
            )
        except ForbiddenError as exc:
            # Bot blocked (v1 / emoji) — block the redirect
            return JSONResponse(
                {"error_code": "403", "error_message": str(exc), "host_url": host_url},
                status_code=403,
            )
        except Exception:
            log.exception("click_tracking_failed", short_code=short_code, schema=schema)

    # 4. Redirect
    resp = RedirectResponse(url_data.long_url, status_code=302)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@router.post("/{short_code}/password")
@limiter.limit("10 per minute; 30 per hour")
async def check_password(
    short_code: str,
    request: Request,
    url_service: UrlService = Depends(get_url_service),
) -> Response:
    """Verify a password for a password-protected URL.

    On success: redirect to /<short_code>?password=<password>.
    On failure: re-render password.html with error message.
    """
    short_code = unquote(short_code)
    form_data = await request.form()
    password = form_data.get("password")
    host_url = str(request.base_url)

    try:
        url_data, schema = await url_service.resolve(short_code)
    except (NotFoundError, ForbiddenError, GoneError):
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "error_code": "400",
                "error_message": "Invalid short code or URL not password-protected",
                "host_url": host_url,
            },
            status_code=400,
        )

    if not url_data.password_hash:
        return templates.TemplateResponse(
            request,
            "error.html",
            {
                "error_code": "400",
                "error_message": "Invalid short code or URL not password-protected",
                "host_url": host_url,
            },
            status_code=400,
        )

    if _check_url_password(password, url_data.password_hash, schema):
        return RedirectResponse(f"/{short_code}?password={password}", status_code=302)

    # Wrong password — re-render password form with error
    return templates.TemplateResponse(
        request,
        "password.html",
        {"short_code": short_code, "error": "Incorrect password", "host_url": host_url},
    )
