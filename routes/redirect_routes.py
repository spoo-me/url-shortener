"""
Redirect routes — the hot path.

GET  /<short_code>          → resolve + redirect (rate-limit exempt)
POST /<short_code>/password → password form submission
"""

from __future__ import annotations

import time
from urllib.parse import unquote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from dependencies import ClickSvc, UrlSvc
from errors import (
    BlockedUrlError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    ValidationError,
)
from infrastructure.logging import get_logger, should_sample
from infrastructure.templates import templates
from middleware.rate_limiter import Limits, limiter
from schemas.models.url import SchemaVersion
from shared.ip_utils import get_client_ip

log = get_logger(__name__)

router = APIRouter()


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


@router.api_route("/{short_code}", methods=["GET", "HEAD"], include_in_schema=False)
@limiter.exempt
async def redirect_url(
    short_code: str,
    request: Request,
    url_service: UrlSvc,
    click_service: ClickSvc,
) -> Response:
    """Resolve a short code and redirect to the destination URL.

    Rate-limit exempt — this is the hot path (~400k requests/day).
    """
    short_code = unquote(short_code)
    user_ip = get_client_ip(request)
    start_time = time.perf_counter()
    host_url = str(request.base_url)

    # 1. Resolve URL (cache-first)
    resolve_start = time.perf_counter()
    try:
        url_data, schema = await url_service.resolve(short_code)
    except NotFoundError:
        log.info("url_not_found", short_code=short_code)
        return _error_page(request, "404", "URL NOT FOUND", 404)
    except BlockedUrlError:
        log.info("url_blocked", short_code=short_code)
        return _error_page(request, "451", "THIS URL HAS BEEN BLOCKED", 451)
    except GoneError:
        log.info("url_gone", short_code=short_code)
        return _error_page(request, "410", "SHORT URL EXPIRED", 410)
    resolve_ms = int((time.perf_counter() - resolve_start) * 1000)

    # 2. Password check
    if url_data.password_hash:
        password = request.query_params.get("password")
        if not url_data.verify_password(password):
            log.debug("url_password_required", short_code=short_code, schema=schema)
            return templates.TemplateResponse(
                request,
                "password.html",
                {"short_code": short_code, "host_url": host_url},
                status_code=401,
            )

    # 3. Track click — skip for HEAD / OPTIONS
    tracking_ms = 0
    if request.method not in ("HEAD", "OPTIONS"):
        user_agent = request.headers.get("User-Agent", "")
        referrer = request.headers.get("Referer")
        cf_city = request.headers.get("CF-IPCity")
        is_emoji = schema == SchemaVersion.EMOJI
        tracking_start = time.perf_counter()
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
            log.info(
                "click_tracking_validation_error", short_code=short_code, schema=schema
            )
        except ForbiddenError as exc:
            # Bot blocked (v1 / emoji) — block the redirect
            log.info(
                "click_tracking_bot_blocked", short_code=short_code, reason=str(exc)
            )
            return _error_page(request, "403", "ACCESS DENIED", 403)
        except Exception:
            log.exception("click_tracking_failed", short_code=short_code, schema=schema)
        tracking_ms = int((time.perf_counter() - tracking_start) * 1000)

    # 4. Redirect
    total_ms = int((time.perf_counter() - start_time) * 1000)
    if should_sample("url_redirect"):
        log.info(
            "url_redirect",
            short_code=short_code,
            schema=schema,
            resolve_ms=resolve_ms,
            tracking_ms=tracking_ms,
            total_ms=total_ms,
        )
    resp = RedirectResponse(url_data.long_url, status_code=302)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@router.post("/{short_code}/password", include_in_schema=False)
@limiter.limit(Limits.PASSWORD_CHECK)
async def check_password(
    short_code: str,
    request: Request,
    url_service: UrlSvc,
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
        url_data, _schema = await url_service.resolve(short_code)
    except (NotFoundError, BlockedUrlError, ForbiddenError, GoneError):
        return _error_page(
            request, "400", "Invalid short code or URL not password-protected", 400
        )

    if not url_data.password_hash:
        return _error_page(
            request, "400", "Invalid short code or URL not password-protected", 400
        )

    if url_data.verify_password(password):
        log.info("url_password_verified", short_code=short_code)
        return RedirectResponse(f"/{short_code}?password={password}", status_code=302)

    # Wrong password — re-render password form with error
    log.info("url_password_incorrect", short_code=short_code)
    return templates.TemplateResponse(
        request,
        "password.html",
        {"short_code": short_code, "error": "Incorrect password", "host_url": host_url},
    )
