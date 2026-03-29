"""Unit tests for ProfilePictureService."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/")

from bson import ObjectId

from errors import NotFoundError
from services.profile_picture_service import ProfilePictureService


def _make_provider(provider="google", picture="https://img.example.com/pic.jpg"):
    p = MagicMock()
    p.provider = provider
    p.provider_user_id = "uid123"
    p.email = "user@example.com"
    p.linked_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    p.profile = MagicMock()
    p.profile.picture = picture
    return p


def _make_user_doc(pfp_url=None, providers=None):
    doc = MagicMock()
    doc.id = ObjectId()
    doc.email = "user@example.com"
    doc.email_verified = True
    doc.user_name = "testuser"
    doc.plan = "free"
    doc.password_set = True
    doc.auth_providers = providers or []
    if pfp_url:
        doc.pfp = MagicMock()
        doc.pfp.url = pfp_url
        doc.pfp.source = "google"
    else:
        doc.pfp = None
    return doc


def _make_service(user_doc=None):
    repo = MagicMock()
    repo.find_by_id = AsyncMock(return_value=user_doc)
    repo.update = AsyncMock()
    return ProfilePictureService(repo), repo


# ── get_dashboard_profile ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_dashboard_profile_returns_correct_shape():
    provider = _make_provider()
    user = _make_user_doc(
        pfp_url="https://img.example.com/pic.jpg", providers=[provider]
    )
    svc, _ = _make_service(user)
    profile = await svc.get_dashboard_profile(user.id)
    assert profile["email"] == "user@example.com"
    assert profile["email_verified"] is True
    assert profile["plan"] == "free"
    assert profile["password_set"] is True
    assert len(profile["auth_providers"]) == 1
    assert profile["auth_providers"][0]["provider"] == "google"
    assert "pfp" in profile
    assert profile["pfp"]["url"] == "https://img.example.com/pic.jpg"


@pytest.mark.asyncio
async def test_get_dashboard_profile_no_pfp():
    user = _make_user_doc()
    svc, _ = _make_service(user)
    profile = await svc.get_dashboard_profile(user.id)
    assert "pfp" not in profile


@pytest.mark.asyncio
async def test_get_dashboard_profile_user_not_found():
    svc, _ = _make_service(None)
    result = await svc.get_dashboard_profile(ObjectId())
    assert result is None


# ── get_available_pictures ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_available_pictures_returns_provider_pictures():
    p1 = _make_provider("google", "https://google.com/pic.jpg")
    p2 = _make_provider("github", "https://github.com/pic.jpg")
    user = _make_user_doc(providers=[p1, p2])
    svc, _ = _make_service(user)
    pics = await svc.get_available_pictures(user.id)
    assert len(pics) == 2
    assert pics[0]["source"] == "google"
    assert pics[1]["source"] == "github"


@pytest.mark.asyncio
async def test_get_available_pictures_marks_current():
    p = _make_provider("google", "https://google.com/pic.jpg")
    user = _make_user_doc(pfp_url="https://google.com/pic.jpg", providers=[p])
    svc, _ = _make_service(user)
    pics = await svc.get_available_pictures(user.id)
    assert pics[0]["is_current"] is True


@pytest.mark.asyncio
async def test_get_available_pictures_skips_no_picture():
    p = _make_provider("google", None)
    user = _make_user_doc(providers=[p])
    svc, _ = _make_service(user)
    pics = await svc.get_available_pictures(user.id)
    assert len(pics) == 0


@pytest.mark.asyncio
async def test_get_available_pictures_user_not_found():
    svc, _ = _make_service(None)
    with pytest.raises(NotFoundError):
        await svc.get_available_pictures(ObjectId())


# ── set_picture ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_picture_updates_pfp():
    p = _make_provider("google", "https://google.com/pic.jpg")
    user = _make_user_doc(providers=[p])
    svc, repo = _make_service(user)
    await svc.set_picture(user.id, "google_uid123")
    repo.update.assert_called_once()
    call_args = repo.update.call_args
    assert call_args[0][0] == user.id
    assert "$set" in call_args[0][1]
    assert call_args[0][1]["$set"]["pfp"]["url"] == "https://google.com/pic.jpg"


@pytest.mark.asyncio
async def test_set_picture_invalid_id_raises():
    p = _make_provider("google", "https://google.com/pic.jpg")
    user = _make_user_doc(providers=[p])
    svc, _ = _make_service(user)
    with pytest.raises(NotFoundError, match="Picture not found"):
        await svc.set_picture(user.id, "invalid_id")


@pytest.mark.asyncio
async def test_set_picture_user_not_found_raises():
    svc, _ = _make_service(None)
    with pytest.raises(NotFoundError, match="User not found"):
        await svc.set_picture(ObjectId(), "google_uid123")


@pytest.mark.asyncio
async def test_set_picture_rejects_arbitrary_url():
    """Cannot set a picture_id that doesn't match any auth provider."""
    p = _make_provider("google", "https://google.com/pic.jpg")
    user = _make_user_doc(providers=[p])
    svc, repo = _make_service(user)
    with pytest.raises(NotFoundError):
        await svc.set_picture(user.id, "evil_attacker_id")
    repo.update.assert_not_called()
