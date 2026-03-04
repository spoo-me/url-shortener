"""API v1 routes package."""

from fastapi import APIRouter

from routes.api_v1 import exports, keys, management, shorten, stats, urls

router = APIRouter(prefix="/api/v1")
router.include_router(shorten.router)
router.include_router(urls.router)
router.include_router(management.router)
router.include_router(stats.router)
router.include_router(exports.router)
router.include_router(keys.router)
