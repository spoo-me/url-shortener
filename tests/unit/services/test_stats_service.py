"""Unit tests for Phase 9 — StatsService."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from errors import AuthenticationError, ForbiddenError, NotFoundError, ValidationError

# ── Constants ────────────────────────────────────────────────────────────────

OWNER_ID = "aaaaaaaaaaaaaaaaaaaaaaaa"

NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
START = NOW - timedelta(days=7)


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


# ── Tests: date defaults and validation ──────────────────────────────────────


class TestDateHandling:
    @pytest.mark.asyncio
    async def test_default_date_range_applied_when_none(self):
        """When start/end are None, a 7-day window ending now is applied."""
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc123",
            start_date=None,
            end_date=None,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
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
                owner_id=OWNER_ID,
                scope="anon",
                short_code="abc",
                start_date=future,
                end_date=NOW,
                filters={},
                group_by=["time"],
                metrics=["clicks"],
                tz_name="UTC",
            )

    @pytest.mark.asyncio
    async def test_date_range_exceeding_90_days_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()

        with pytest.raises(ValidationError, match="date range cannot exceed 90 days"):
            await svc.query(
                owner_id=OWNER_ID,
                scope="anon",
                short_code="abc",
                start_date=NOW - timedelta(days=95),
                end_date=NOW,
                filters={},
                group_by=["time"],
                metrics=["clicks"],
                tz_name="UTC",
            )


# ── Tests: scope / privacy ────────────────────────────────────────────────────


class TestScopeValidation:
    @pytest.mark.asyncio
    async def test_anon_scope_requires_short_code(self):
        svc, _, _ = make_service()

        with pytest.raises(ValidationError, match="short_code is required"):
            await svc.query(
                owner_id=None,
                scope="anon",
                short_code=None,
                start_date=START,
                end_date=NOW,
                filters={},
                group_by=["time"],
                metrics=["clicks"],
                tz_name="UTC",
            )

    @pytest.mark.asyncio
    async def test_anon_scope_short_code_not_found_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(exists=False)

        with pytest.raises(NotFoundError):
            await svc.query(
                owner_id=None,
                scope="anon",
                short_code="ghost",
                start_date=START,
                end_date=NOW,
                filters={},
                group_by=["time"],
                metrics=["clicks"],
                tz_name="UTC",
            )

    @pytest.mark.asyncio
    async def test_anon_scope_private_stats_unauthenticated_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(
            private=True, owner_id=OWNER_ID
        )

        with pytest.raises(AuthenticationError):
            await svc.query(
                owner_id=None,  # not logged in
                scope="anon",
                short_code="secret",
                start_date=START,
                end_date=NOW,
                filters={},
                group_by=["time"],
                metrics=["clicks"],
                tz_name="UTC",
            )

    @pytest.mark.asyncio
    async def test_anon_scope_private_stats_wrong_owner_raises(self):
        svc, _, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(
            private=True, owner_id="different_owner_id"
        )

        with pytest.raises(ForbiddenError):
            await svc.query(
                owner_id=OWNER_ID,  # authenticated but not the owner
                scope="anon",
                short_code="secret",
                start_date=START,
                end_date=NOW,
                filters={},
                group_by=["time"],
                metrics=["clicks"],
                tz_name="UTC",
            )

    @pytest.mark.asyncio
    async def test_anon_scope_private_stats_correct_owner_succeeds(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info(
            private=True, owner_id=OWNER_ID
        )
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="secret",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
        )
        assert result["scope"] == "anon"

    @pytest.mark.asyncio
    async def test_all_scope_requires_auth(self):
        svc, _, _ = make_service()

        with pytest.raises(AuthenticationError):
            await svc.query(
                owner_id=None,
                scope="all",
                short_code=None,
                start_date=START,
                end_date=NOW,
                filters={},
                group_by=["time"],
                metrics=["clicks"],
                tz_name="UTC",
            )

    @pytest.mark.asyncio
    async def test_all_scope_with_auth_succeeds(self):
        svc, click_repo, _ = make_service()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            owner_id=OWNER_ID,
            scope="all",
            short_code=None,
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
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
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time", "browser"],
            metrics=["clicks"],
            tz_name="UTC",
        )
        click_repo.aggregate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_pipeline_starts_with_match(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
        )
        pipeline = click_repo.aggregate.call_args[0][0]
        assert pipeline[0].get("$match") is not None

    @pytest.mark.asyncio
    async def test_pipeline_has_facet_stage(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["browser", "country"],
            metrics=["clicks"],
            tz_name="UTC",
        )
        pipeline = click_repo.aggregate.call_args[0][0]
        assert pipeline[1].get("$facet") is not None

    @pytest.mark.asyncio
    async def test_facet_contains_summary_and_requested_dimensions(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["browser", "os"],
            metrics=["clicks"],
            tz_name="UTC",
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
            owner_id=OWNER_ID,
            scope="all",
            short_code=None,
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
        )
        match = click_repo.aggregate.call_args[0][0][0]["$match"]
        assert match["meta.owner_id"] == ObjectId(OWNER_ID)

    @pytest.mark.asyncio
    async def test_scope_anon_adds_short_code_to_match(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="mycode",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
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
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
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
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
        )
        assert result["summary"]["total_clicks"] == 50
        assert result["summary"]["unique_clicks"] == 20

    @pytest.mark.asyncio
    async def test_computed_metrics_added_when_clicks_exist(self):
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response(total=100, unique=40)

        result = await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
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
            owner_id=OWNER_ID,
            scope="anon",
            short_code="mycode",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="UTC",
        )
        assert result["short_code"] == "mycode"

    @pytest.mark.asyncio
    async def test_no_results_returns_empty_metrics(self):
        """When aggregate returns nothing, metrics lists are empty."""
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = []  # no data

        result = await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["browser"],
            metrics=["clicks"],
            tz_name="UTC",
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
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="Not/ATimezone",
        )
        assert result["timezone"] == "UTC"

    @pytest.mark.asyncio
    async def test_timezone_alias_is_normalised(self):
        """Legacy timezone aliases like Asia/Calcutta → Asia/Kolkata."""
        svc, click_repo, url_repo = make_service()
        url_repo.check_stats_privacy.return_value = privacy_info()
        click_repo.aggregate.return_value = facet_response()

        result = await svc.query(
            owner_id=OWNER_ID,
            scope="anon",
            short_code="abc",
            start_date=START,
            end_date=NOW,
            filters={},
            group_by=["time"],
            metrics=["clicks"],
            tz_name="Asia/Calcutta",
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
