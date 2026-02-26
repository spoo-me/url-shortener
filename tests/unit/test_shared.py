"""
Unit tests for the shared/ utility modules.

Covers:
- shared.validators      (validate_url, validate_url_password, validate_alias,
                          validate_emoji_alias, validate_blocked_url)
- shared.generators      (generate_short_code, generate_short_code_v2,
                          generate_emoji_alias, generate_otp_code,
                          generate_secure_token)
- shared.datetime_utils  (parse_datetime, convert_to_gmt)
- shared.ip_utils        (get_client_ip)
- shared.crypto          (hash_password, verify_password, hash_token)
- shared.bot_detection   (is_bot_request, get_bot_name)
- shared.time_bucket_utils (determine_optimal_bucket_strategy,
                            fill_missing_buckets)
"""

from __future__ import annotations

import hashlib
import re
import string
from datetime import datetime, timezone
from unittest.mock import MagicMock

import emoji as _emoji
import pytest

from shared.bot_detection import get_bot_name, is_bot_request
from shared.crypto import hash_password, hash_token, verify_password
from shared.datetime_utils import convert_to_gmt, parse_datetime
from shared.generators import (
    generate_emoji_alias,
    generate_otp_code,
    generate_secure_token,
    generate_short_code,
    generate_short_code_v2,
)
from shared.ip_utils import get_client_ip
from shared.time_bucket_utils import (
    BUCKET_CONFIGS,
    TimeBucketStrategy,
    determine_optimal_bucket_strategy,
    fill_missing_buckets,
)
from shared.validators import (
    validate_alias,
    validate_blocked_url,
    validate_emoji_alias,
    validate_url,
    validate_url_password,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(headers: dict, client_host: str = "10.0.0.1") -> MagicMock:
    """Minimal mock of a FastAPI Request."""
    req = MagicMock()
    req.headers = headers
    req.client = MagicMock()
    req.client.host = client_host
    return req


# ---------------------------------------------------------------------------
# shared.validators — validate_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://example.com", True),
        ("https://example.com/foo/bar?q=1", True),
        ("https://spoo.me/abc", False),
        ("https://SPOO.ME/abc", False),  # case-insensitive block
        ("not-a-url", False),
        ("http://192.168.1.1/path", False),  # IPv4 skipped by validator
    ],
    ids=[
        "valid",
        "valid_with_path",
        "self_ref",
        "self_ref_uppercase",
        "plain_text",
        "ipv4",
    ],
)
def test_validate_url(url, expected):
    assert validate_url(url) is expected


def test_validate_url_custom_blocked_domain():
    assert validate_url("https://evil.com", blocked_self_domains=("evil.com",)) is False


def test_validate_url_empty_blocked_list_allows_spoo():
    assert validate_url("https://spoo.me/x", blocked_self_domains=()) is True


# ---------------------------------------------------------------------------
# shared.validators — validate_url_password
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password, valid",
    [
        ("Hello123.", True),
        ("Hello123@", True),
        ("Hi1.", False),  # too short
        ("12345678.", False),  # no letter
        ("HelloWorld.", False),  # no digit
        ("Hello1234", False),  # no special char
        ("Hello12..", False),  # consecutive specials (..)
        ("Hello12@.", False),  # consecutive specials (@.)
    ],
    ids=[
        "dot_ok",
        "at_ok",
        "too_short",
        "no_letter",
        "no_digit",
        "no_special",
        "consecutive_dots",
        "consecutive_at_dot",
    ],
)
def test_validate_url_password(password, valid):
    assert validate_url_password(password) is valid


# ---------------------------------------------------------------------------
# shared.validators — validate_alias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alias, expected",
    [
        ("MyAlias123", True),
        ("my_alias", True),
        ("my-alias", True),
        ("", True),  # zero chars matches *
        ("my alias", False),  # space
        ("alias!", False),  # special char
    ],
    ids=["alphanumeric", "underscore", "hyphen", "empty", "space", "exclamation"],
)
def test_validate_alias(alias, expected):
    assert validate_alias(alias) is expected


# ---------------------------------------------------------------------------
# shared.validators — validate_emoji_alias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alias, expected",
    [
        ("😀😃😄", True),
        ("😀", True),
        ("hello", False),  # plain text
        ("hello😀", False),  # mixed
        ("😀" * 16, False),  # exceeds 15-emoji limit
        ("😀" * 15, True),  # exactly at limit
    ],
    ids=["three_emojis", "single", "plain_text", "mixed", "over_limit", "at_limit"],
)
def test_validate_emoji_alias(alias, expected):
    assert validate_emoji_alias(alias) is expected


# ---------------------------------------------------------------------------
# shared.validators — validate_blocked_url
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, patterns, expected",
    [
        ("https://evil.com", [], True),  # no patterns → always allow
        ("https://phishing.example.com", [r"phishing"], False),  # match → block
        ("https://good.example.com", [r"phishing"], True),  # no match → allow
        ("https://spam.ru/page", [r"\.ru/"], False),  # regex applied
        ("https://evil.com", [r"safe", r"evil"], False),  # second pattern matches
    ],
    ids=[
        "no_patterns",
        "match_blocks",
        "no_match_allows",
        "regex_match",
        "second_pattern",
    ],
)
def test_validate_blocked_url(url, patterns, expected):
    assert validate_blocked_url(url, patterns) is expected


def test_validate_blocked_url_timeout_fails_open(mocker):
    """Timed-out patterns must fail open (URL stays allowed)."""
    mocker.patch("shared.validators.regex.search", side_effect=TimeoutError)
    assert validate_blocked_url("https://example.com", [r"any_pattern"]) is True


# ---------------------------------------------------------------------------
# shared.generators
# ---------------------------------------------------------------------------


_ALPHANUM = set(string.ascii_letters + string.digits)


class TestGenerateShortCode:
    def test_length_is_6(self):
        assert len(generate_short_code()) == 6

    def test_only_alphanumeric(self):
        assert set(generate_short_code()).issubset(_ALPHANUM)

    def test_produces_variety(self):
        assert len({generate_short_code() for _ in range(20)}) > 1


class TestGenerateShortCodeV2:
    def test_default_length_is_7(self):
        assert len(generate_short_code_v2()) == 7

    @pytest.mark.parametrize("length", [4, 8, 12, 20])
    def test_custom_length(self, length):
        assert len(generate_short_code_v2(length=length)) == length

    def test_only_alphanumeric(self):
        assert set(generate_short_code_v2()).issubset(_ALPHANUM)


class TestGenerateEmojiAlias:
    def test_returns_exactly_3_emojis(self):
        assert len(_emoji.emoji_list(generate_emoji_alias())) == 3

    def test_produces_variety(self):
        assert len({generate_emoji_alias() for _ in range(20)}) > 1


class TestGenerateOtpCode:
    @pytest.mark.parametrize("length", [4, 6, 8])
    def test_length(self, length):
        assert len(generate_otp_code(length=length)) == length

    def test_only_digits(self):
        assert generate_otp_code().isdigit()


class TestGenerateSecureToken:
    def test_url_safe_characters(self):
        assert re.match(r"^[A-Za-z0-9_\-]+$", generate_secure_token())

    def test_produces_variety(self):
        assert len({generate_secure_token() for _ in range(10)}) > 1


# ---------------------------------------------------------------------------
# shared.datetime_utils — parse_datetime
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, None),
        (0, datetime(1970, 1, 1, tzinfo=timezone.utc)),
        (1000.5, datetime(1970, 1, 1, 0, 16, 40, tzinfo=timezone.utc)),
        ("2024-01-15T12:00:00Z", datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)),
        (
            "2024-01-15T14:00:00+02:00",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        ),
        (
            "2024-01-15T12:00:00+05:30",
            datetime(2024, 1, 15, 6, 30, 0, tzinfo=timezone.utc),
        ),
        ("not-a-date", None),
    ],
    ids=[
        "none",
        "epoch_int",
        "epoch_float",
        "iso_z",
        "iso_offset",
        "iso_offset_india",
        "invalid",
    ],
)
def test_parse_datetime(value, expected):
    assert parse_datetime(value) == expected


def test_parse_datetime_naive_assumed_utc():
    dt = parse_datetime("2024-06-01T00:00:00")
    assert dt is not None and dt.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# shared.datetime_utils — convert_to_gmt
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (
            "2024-01-15T14:00:00+02:00",
            datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        ),
        (
            "2024-06-01T00:00:00+00:00",
            datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
        ),
        ("2024-01-15T14:00:00", None),  # naive → None
    ],
    ids=["offset_converted", "utc_unchanged", "naive_returns_none"],
)
def test_convert_to_gmt(value, expected):
    assert convert_to_gmt(value) == expected


# ---------------------------------------------------------------------------
# shared.ip_utils — get_client_ip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "headers, client_host, expected_ip",
    [
        (
            {"CF-Connecting-IP": "1.2.3.4", "X-Real-IP": "9.9.9.9"},
            "10.0.0.1",
            "1.2.3.4",
        ),
        ({"True-Client-IP": "5.6.7.8"}, "10.0.0.1", "5.6.7.8"),
        ({"X-Forwarded-For": "11.22.33.44, 99.99.99.99"}, "10.0.0.1", "11.22.33.44"),
        ({"X-Real-IP": "55.66.77.88"}, "10.0.0.1", "55.66.77.88"),
        ({}, "192.168.1.50", "192.168.1.50"),  # fallback to client.host
    ],
    ids=[
        "cloudflare",
        "true_client_ip",
        "x_forwarded_for_multi",
        "x_real_ip",
        "fallback",
    ],
)
def test_get_client_ip(headers, client_host, expected_ip):
    assert get_client_ip(_make_request(headers, client_host)) == expected_ip


def test_get_client_ip_no_client_returns_empty():
    req = MagicMock()
    req.headers = {}
    req.client = None
    assert get_client_ip(req) == ""


# ---------------------------------------------------------------------------
# shared.crypto
# ---------------------------------------------------------------------------


class TestHashPassword:
    def test_returns_string(self):
        assert isinstance(hash_password("secret"), str)

    def test_differs_from_input(self):
        assert hash_password("secret") != "secret"

    def test_unique_salts(self):
        # argon2 produces a new salt each call
        assert hash_password("same") != hash_password("same")


class TestVerifyPassword:
    @pytest.mark.parametrize(
        "candidate, expected",
        [("correct_password", True), ("wrong_password", False)],
        ids=["correct", "wrong"],
    )
    def test_verify(self, candidate, expected):
        h = hash_password("correct_password")
        assert verify_password(candidate, h) is expected

    def test_invalid_hash_returns_false(self):
        assert verify_password("any", "not-a-valid-hash") is False


@pytest.mark.parametrize(
    "token",
    ["abc", "test", "some_token", "token_with_unicode_🔑"],
    ids=["short", "simple", "with_underscore", "unicode"],
)
def test_hash_token_is_hex64(token):
    h = hash_token(token)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_token_deterministic():
    assert hash_token("abc") == hash_token("abc")


def test_hash_token_known_value():
    assert hash_token("test") == hashlib.sha256(b"test").hexdigest()


def test_hash_token_distinct_inputs():
    assert hash_token("token_a") != hash_token("token_b")


# ---------------------------------------------------------------------------
# shared.bot_detection
# ---------------------------------------------------------------------------


GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
)
CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


class TestIsBotRequest:
    def test_googlebot_detected(self):
        assert is_bot_request(GOOGLEBOT_UA) is True

    def test_normal_browser_not_bot(self):
        assert is_bot_request(CHROME_UA) is False

    def test_custom_pattern_match(self, mocker):
        mocker.patch(
            "shared.bot_detection._load_bot_user_agents", return_value=["TestBot/1\\.0"]
        )
        mocker.patch(
            "shared.bot_detection._crawler_detect"
        ).isCrawler.return_value = False
        assert is_bot_request("TestBot/1.0 (test)") is True

    def test_falls_back_to_crawler_detect_when_no_patterns(self, mocker):
        mocker.patch("shared.bot_detection._load_bot_user_agents", return_value=[])
        assert is_bot_request(GOOGLEBOT_UA) is True


class TestGetBotName:
    def test_non_bot_returns_none(self):
        assert get_bot_name(CHROME_UA) is None

    def test_googlebot_returns_string(self):
        name = get_bot_name(GOOGLEBOT_UA)
        assert name is not None and isinstance(name, str)

    def test_pattern_match_returns_pattern(self, mocker):
        mocker.patch(
            "shared.bot_detection._load_bot_user_agents", return_value=["MyCustomBot"]
        )
        mock_cd = mocker.patch("shared.bot_detection._crawler_detect")
        mock_cd.isCrawler.return_value = False
        mock_cd.getMatches.return_value = None
        assert get_bot_name("MyCustomBot/2.0") == "MyCustomBot"


# ---------------------------------------------------------------------------
# shared.time_bucket_utils
# ---------------------------------------------------------------------------


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
