from __future__ import annotations

from datetime import datetime

import pytest

from shared.time_bucket_utils import (
    BUCKET_CONFIGS,
    TimeBucketStrategy,
    determine_optimal_bucket_strategy,
    fill_missing_buckets,
)


@pytest.mark.parametrize(
    "start, end, expected",
    [
        (None, None, TimeBucketStrategy.DAILY),
        (
            datetime(2024, 1, 1, 12, 0),
            datetime(2024, 1, 1, 12, 30),
            TimeBucketStrategy.MINUTE_10,
        ),
        (
            datetime(2024, 1, 1, 12, 0),
            datetime(2024, 1, 1, 13, 0),
            TimeBucketStrategy.MINUTE_10,
        ),  # boundary
        (
            datetime(2024, 1, 1, 0, 0),
            datetime(2024, 1, 1, 12, 0),
            TimeBucketStrategy.HOURLY,
        ),
        (datetime(2024, 1, 1), datetime(2024, 1, 8), TimeBucketStrategy.DAILY),
    ],
    ids=["no_dates", "30min", "exactly_1hr", "12hrs", "7days"],
)
def test_determine_optimal_bucket_strategy(start, end, expected):
    assert determine_optimal_bucket_strategy(start, end) == expected


class TestFillMissingBuckets:
    def test_fills_gap_with_zeros(self):
        config = BUCKET_CONFIGS[TimeBucketStrategy.DAILY]
        actual = [
            {"date": "2024-01-01", "total_clicks": 5, "unique_clicks": 3},
            {"date": "2024-01-03", "total_clicks": 2, "unique_clicks": 2},
        ]
        result = fill_missing_buckets(
            actual, datetime(2024, 1, 1), datetime(2024, 1, 3), config
        )
        dates = [r["date"] for r in result]
        assert "2024-01-02" in dates
        filled = next(r for r in result if r["date"] == "2024-01-02")
        assert filled["total_clicks"] == 0 and filled["unique_clicks"] == 0

    def test_empty_actuals_produces_all_zeros(self):
        config = BUCKET_CONFIGS[TimeBucketStrategy.DAILY]
        result = fill_missing_buckets(
            [], datetime(2024, 1, 1), datetime(2024, 1, 3), config
        )
        assert len(result) == 3
        assert all(r["total_clicks"] == 0 for r in result)
