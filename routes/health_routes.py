"""
Health check endpoint.

GET /health — checks MongoDB and Redis connectivity.
Rules:
- MongoDB failure → "unhealthy" (503) — the app cannot function without it.
- Redis failure or absence → "degraded" (200) — Redis is optional.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from middleware.openapi import PUBLIC_SECURITY

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    openapi_extra=PUBLIC_SECURITY,
    operation_id="healthCheck",
    summary="Health Check",
)
async def health_check(request: Request) -> JSONResponse:
    """Check the health of the application and its dependencies.

    Pings MongoDB and Redis to determine overall system status:

    - **healthy** (200): Both MongoDB and Redis are reachable.
    - **degraded** (200): MongoDB is reachable but Redis is down or not configured.
    - **unhealthy** (503): MongoDB is unreachable -- the app cannot function.

    **Authentication**: Not required (public endpoint)

    **Rate Limits**: None
    """
    checks: dict[str, str] = {}
    overall = "healthy"

    try:
        db = request.app.state.db
        await db.client.admin.command("ping")
        checks["mongodb"] = "ok"
    except Exception:
        checks["mongodb"] = "error"
        overall = "unhealthy"

    redis = request.app.state.redis
    if redis is None:
        checks["redis"] = "not_configured"
        if overall == "healthy":
            overall = "degraded"
    else:
        try:
            await redis.ping()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "error"
            if overall == "healthy":
                overall = "degraded"

    status_code = 503 if overall == "unhealthy" else 200
    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "checks": checks},
    )
