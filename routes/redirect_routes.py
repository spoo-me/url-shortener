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
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from dependencies import get_click_service, get_url_service
from errors import ForbiddenError, GoneError, NotFoundError, ValidationError
from middleware.rate_limiter import Limits, limiter
from services.click import ClickService
from services.url_service import UrlService
from shared.crypto import verify_password
from shared.ip_utils import get_client_ip
from shared.logging import get_logger, should_sample

log = get_logger(__name__)

router = APIRouter()

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)


def _error_page(request: Request, code: str, message: str, status: int) -> Response:
    """Render error.html with consistent structure."""
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "error_code": code,
            "error_message": message,
            "host_url": str(request.base_url),
        },
        status_code=status,
    )


def _check_url_password(password: str | None, password_hash: str, schema: str) -> bool:
    """Verify a URL password — bcrypt for v2, plaintext comparison for v1/emoji."""
    if schema == "v2":
        return verify_password(password or "", password_hash)
    return password == password_hash


@router.api_route("/{short_code}", methods=["GET", "HEAD"], include_in_schema=False)
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
        log.info("url_not_found", short_code=short_code)
        return _error_page(request, "404", "URL NOT FOUND", 404)
    except ForbiddenError:
        log.warning("url_blocked", short_code=short_code)
        return _error_page(request, "403", "ACCESS DENIED", 403)
    except GoneError:
        log.info("url_gone", short_code=short_code)
        return _error_page(request, "410", "SHORT URL EXPIRED", 410)

    # 2. Password check
    if url_data.password_hash:
        password = request.query_params.get("password")
        if not _check_url_password(password, url_data.password_hash, schema):
            log.debug("url_password_required", short_code=short_code, schema=schema)
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
            log.warning(
                "click_tracking_bot_blocked", short_code=short_code, reason=str(exc)
            )
            return _error_page(request, "403", "ACCESS DENIED", 403)
        except Exception:
            log.exception("click_tracking_failed", short_code=short_code, schema=schema)

    # 4. Redirect
    if should_sample("url_redirect"):
        log.info(
            "url_redirect",
            short_code=short_code,
            schema=schema,
            duration_ms=int((time.perf_counter() - start_time) * 1000),
        )
    resp = RedirectResponse(url_data.long_url, status_code=302)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@router.post("/{short_code}/password", include_in_schema=False)
@limiter.limit(Limits.PASSWORD_CHECK)
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
        return _error_page(
            request, "400", "Invalid short code or URL not password-protected", 400
        )

    if not url_data.password_hash:
        return _error_page(
            request, "400", "Invalid short code or URL not password-protected", 400
        )

    if _check_url_password(password, url_data.password_hash, schema):
        log.info("url_password_verified", short_code=short_code)
        return RedirectResponse(f"/{short_code}?password={password}", status_code=302)

    # Wrong password — re-render password form with error
    log.warning("url_password_incorrect", short_code=short_code)
    return templates.TemplateResponse(
        request,
        "password.html",
        {"short_code": short_code, "error": "Incorrect password", "host_url": host_url},
    )
