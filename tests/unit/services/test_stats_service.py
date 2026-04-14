"""Unit tests for Phase 9 — StatsService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from errors import AuthenticationError, ForbiddenError, NotFoundError, ValidationError
from schemas.dto.requests.stats import StatsQuery

# ── Constants ────────────────────────────────────────────────────────────────

OWNER_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=7)

NOW_ISO = NOW.isoformat()
START_ISO = START.isoformat()


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_service():
    from services.stats_service import StatsService

    click_repo = AsyncMock()
    url_repo = AsyncMock()
    # Default: aggregate returns empty (no clicks)
    click_repo.aggregate.return_value = []
    return StatsService(click_repo=click_repo, url_repo=url_repo), click_repo, url_repo


def privacy_info(exists=True, private=False, owner_id=OWNER_ID):
    return {"exists": exists, "private": private, "owner_id": owner_id}


def facet_response(
    total=10,
    unique=5,
    first_click=None,
    last_click=None,
    avg_redirect=120.5,
    dimensions=None,
):
    """Build a fake $facet aggregation result."""
    summary = [
        {
            "total_clicks": total,
            "unique_clicks": unique,
            "first_click": first_click or NOW - timedelta(days=1),
            "last_click": last_click or NOW,
            "avg_redirection_time": avg_redirect,
        }
    ]
    result = {"_summary": summary}
    if dimensions:
        result.update(dimensions)
    return [result]  # aggregate() returns a list


def _q(
    scope="anon",
    short_code="abc",
    start_date=None,
    end_date=None,
    group_by="time",
    metrics="clicks",
    timezone_="UTC",
    **filter_kw,
):
    """Build a StatsQuery with sensible defaults for tests."""
    return StatsQuery(
        scope=scope,
        short_code=short_code,
        start_date=start_date if start_date is not None else START_ISO,
        end_date=end_date if end_date is not None else NOW_ISO,
        group_by=group_by,
        metrics=metrics,
        timezone=timezone_,
        **filter_kw,
    )


# ── Tests: date defaults and validation ──────────────────────────────────────


class TestDateHandling:
    @pytest.mark.asyncio
    async def test_default_date_range_applied_when_none(self):
        """When start/end are None, a 7-day window ending now is applied."""
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            query=StatsQuery(
                scope="anon",
                short_code="abc123",
                group_by="time",
                metrics="clicks",
                timezone="UTC",
            ),
            owner_id=OWNER_ID,
        )
        assert "time_range" in result
        assert result["time_range"]["start_date"] is not None
        assert result["time_range"]["end_date"] is not None

    @pytest.mark.asyncio
    async def test_start_date_after_end_date_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        future = NOW + timedelta(days=1)

        with pytest.raises(ValidationError, match="start_date must be before end_date"):
            await svc.query(
                query=_q(
                    short_code="abc",
                    start_date=future.isoformat(),
                    end_date=NOW_ISO,
                ),
                owner_id=OWNER_ID,
            )

    @pytest.mark.asyncio
    async def test_date_range_exceeding_90_days_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()

        with pytest.raises(ValidationError, match="date range cannot exceed 90 days"):
            await svc.query(
                query=_q(
                    short_code="abc",
                    start_date=(NOW - timedelta(days=95)).isoformat(),
                    end_date=NOW_ISO,
                ),
                owner_id=OWNER_ID,
            )


# ── Tests: scope / privacy ────────────────────────────────────────────────────


class TestScopeValidation:
    @pytest.mark.asyncio
    async def test_anon_scope_requires_short_code(self):
        svc, _, _ = make_service()

        with pytest.raises(ValidationError, match="short_code is required"):
            await svc.query(
                query=_q(scope="anon", short_code=None),
                owner_id=None,
            )

    @pytest.mark.asyncio
    async def test_anon_scope_short_code_not_found_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(exists=False)

        with pytest.raises(NotFoundError):
            await svc.query(
                query=_q(scope="anon", short_code="ghost"),
                owner_id=None,
            )

    @pytest.mark.asyncio
    async def test_anon_scope_private_stats_unauthenticated_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(
            private=True, owner_id=OWNER_ID
        )

        with pytest.raises(AuthenticationError):
            await svc.query(
                query=_q(scope="anon", short_code="secret"),
                owner_id=None,  # not logged in
            )

    @pytest.mark.asyncio
    async def test_anon_scope_private_stats_wrong_owner_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(
            private=True, owner_id="different_owner_id"
        )

        with pytest.raises(ForbiddenError):
            await svc.query(
                query=_q(scope="anon", short_code="secret"),
                owner_id=OWNER_ID,  # authenticated but not the owner
            )

    @pytest.mark.asyncio
    async def test_anon_scope_private_stats_correct_owner_succeeds(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(
            private=True, owner_id=OWNER_ID
        )
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            query=_q(scope="anon", short_code="secret"),
            owner_id=OWNER_ID,
        )
        assert result["scope"] == "anon"

    @pytest.mark.asyncio
    async def test_all_scope_requires_auth(self):
        svc, _, _ = make_service()

        with pytest.raises(AuthenticationError):
            await svc.query(
                query=_q(scope="all", short_code=None),
                owner_id=None,
            )

    @pytest.mark.asyncio
    async def test_all_scope_with_auth_succeeds(self):
        svc, click_repo, _ = make_service()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            query=_q(scope="all", short_code=None),
            owner_id=OWNER_ID,
        )
        assert result["scope"] == "all"


# ── Tests: aggregation pipeline structure ────────────────────────────────────


class TestAggregationPipeline:
    @pytest.mark.asyncio
    async def test_single_facet_call_made(self):
        """Only one aggregate() call per query (the $facet pipeline)."""
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            query=_q(group_by="time,browser"),
            owner_id=OWNER_ID,
        )
        click_repo.aggregate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_starts_with_match(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            query=_q(),
            owner_id=OWNER_ID,
        )
        pipeline = click_repo.aggregate.call_args[0][0]
        assert pipeline[0].get("$match") is not None

    @pytest.mark.asyncio
    async def test_pipeline_has_facet_stage(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            query=_q(group_by="browser,country"),
            owner_id=OWNER_ID,
        )
        pipeline = click_repo.aggregate.call_args[0][0]
        assert pipeline[1].get("$facet") is not None

    @pytest.mark.asyncio
    async def test_facet_contains_summary_and_requested_dimensions(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            query=_q(group_by="browser,os"),
            owner_id=OWNER_ID,
        )
        facet = click_repo.aggregate.call_args[0][0][1]["$facet"]
        assert "_summary" in facet
        assert "browser" in facet
        assert "os" in facet

    @pytest.mark.asyncio
    async def test_scope_all_adds_owner_id_to_match(self):
        from bson import ObjectId

        svc, click_repo, _ = make_service()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            query=_q(scope="all", short_code=None),
            owner_id=OWNER_ID,
        )
        match = click_repo.aggregate.call_args[0][0][0]["$match"]
        assert match["meta.owner_id"] == ObjectId(OWNER_ID)

    @pytest.mark.asyncio
    async def test_scope_anon_adds_short_code_to_match(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            query=_q(scope="anon", short_code="mycode"),
            owner_id=OWNER_ID,
        )
        match = click_repo.aggregate.call_args[0][0][0]["$match"]
        assert match["meta.short_code"] == "mycode"


# ── Tests: response structure ─────────────────────────────────────────────────


class TestResponseStructure:
    @pytest.mark.asyncio
    async def test_response_has_required_top_level_keys(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            query=_q(),
            owner_id=OWNER_ID,
        )
        for key in (
            "scope",
            "filters",
            "group_by",
            "timezone",
            "metrics",
            "time_range",
            "summary",
            "generated_at",
            "api_version",
        ):
            assert key in result, f"missing key: {key}"

    @pytest.mark.asyncio
    async def test_summary_stats_populated(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response(total=50, unique=20)

        result = await svc.query(
            query=_q(),
            owner_id=OWNER_ID,
        )
        assert result["summary"]["total_clicks"] == 50
        assert result["summary"]["unique_clicks"] == 20

    @pytest.mark.asyncio
    async def test_computed_metrics_added_when_clicks_exist(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response(total=100, unique=40)

        result = await svc.query(
            query=_q(),
            owner_id=OWNER_ID,
        )
        cm = result.get("computed_metrics", {})
        assert cm["unique_click_rate"] == 40.0
        assert cm["repeat_click_rate"] == 60.0

    @pytest.mark.asyncio
    async def test_anon_scope_includes_short_code_in_response(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            query=_q(scope="anon", short_code="mycode"),
            owner_id=OWNER_ID,
        )
        assert result["short_code"] == "mycode"

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_metrics(self):
        """When aggregate returns nothing, metrics lists are empty."""
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = []  # no data

        result = await svc.query(
            query=_q(group_by="browser"),
            owner_id=OWNER_ID,
        )
        assert result["metrics"]["clicks_by_browser"] == []


# ── Tests: timezone handling ──────────────────────────────────────────────────


class TestTimezone:
    @pytest.mark.asyncio
    async def test_invalid_timezone_falls_back_to_utc(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            query=_q(timezone_="Not/ATimezone"),
            owner_id=OWNER_ID,
        )
        assert result["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_timezone_alias_is_normalised(self):
        """Legacy timezone aliases like Asia/Calcutta -> Asia/Kolkata."""
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            query=_q(timezone_="Asia/Calcutta"),
            owner_id=OWNER_ID,
        )
        assert result["timezone"] == "Asia/Kolkata"


# ── Tests: filter query building ─────────────────────────────────────────────


class TestClickQueryBuilding:
    def test_scope_all_produces_owner_id_filter(self):
        from bson import ObjectId

        from services.stats_service import StatsService

        q = StatsService._build_click_query("all", OWNER_ID, None, START, NOW, {})
        assert q["meta.owner_id"] == ObjectId(OWNER_ID)

    def test_scope_anon_produces_short_code_filter(self):
        from services.stats_service import StatsService

        q = StatsService._build_click_query("anon", None, "mycode", START, NOW, {})
        assert q["meta.short_code"] == "mycode"

    def test_time_range_in_query(self):
        from services.stats_service import StatsService

        q = StatsService._build_click_query("all", OWNER_ID, None, START, NOW, {})
        assert q["clicked_at"]["$gte"] == START
        assert q["clicked_at"]["$lte"] == NOW

    def test_dimension_filter_added(self):
        from services.stats_service import StatsService

        q = StatsService._build_click_query(
            "all", OWNER_ID, None, START, NOW, {"browser": ["Chrome", "Firefox"]}
        )
        assert q["browser"] == {"$in": ["Chrome", "Firefox"]}

    def test_referrer_direct_filter_uses_or_clause(self):
        from services.stats_service import StatsService

        q = StatsService._build_click_query(
            "all", OWNER_ID, None, START, NOW, {"referrer": ["Direct"]}
        )
        assert "$or" in q

    def test_short_code_filter_skipped_in_anon_scope(self):
        """short_code filter cannot bypass the scope lock (security)."""
        from services.stats_service import StatsService

        q = StatsService._build_click_query(
            "anon",
            None,
            "locked",
            START,
            NOW,
            {"short_code": ["bypass_attempt"]},
        )
        # meta.short_code must remain the locked value, not the filter value
        assert q["meta.short_code"] == "locked"
        assert "$in" not in str(q.get("meta.short_code", ""))
