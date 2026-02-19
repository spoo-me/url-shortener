from datetime import datetime
from flask.testing import FlaskClient
import pytest
from datetime import timedelta
import urllib.parse


def test_get_request_handling(client):
    response = client.get("/stats")
    assert response.status_code == 200
    assert b"Enter the alias of the short URL" in response.data


def test_get_request_redirect(client):
    response = client.get("/stats/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/stats"


def test_post_no_short_code(client):
    response = client.post("/stats", data={})
    assert response.status_code == 400
    assert response.json == {"error": "Invalid Short Code, short code does not exist!"}


def test_post_invalid_short_code(client, mocker):
    mocker.patch("blueprints.stats.load_url", return_value=None)
    response = client.post("/stats", data={"short_code": "invalidcode"})
    assert response.status_code == 200
    assert b"Invalid Short Code, short code does not exist!" in response.data


def test_post_password_protected_url_without_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url", return_value={"password": "correctpassword"}
    )
    response = client.post("/stats", data={"short_code": "validcode"})
    assert response.status_code == 200
    assert (
        b"is a password protected Url, please enter the password to continue."
        in response.data
    )


def test_post_incorrect_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url", return_value={"password": "correctpassword"}
    )
    response = client.post(
        "/stats", data={"short_code": "validcode", "password": "wrongpassword"}
    )
    assert response.status_code == 200
    assert (
        b"Invalid Password! please enter the correct password to continue."
        in response.data
    )


def test_post_correct_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url", return_value={"password": "correctpassword"}
    )
    response = client.post(
        "/stats", data={"short_code": "validcode", "password": "correctpassword"}
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/stats/validcode?password=correctpassword"


def test_post_valid_short_code_without_password_protection(client, mocker):
    mocker.patch("blueprints.stats.load_url", return_value={"_id": "validcode"})
    response = client.post("/stats", data={"short_code": "validcode"})
    assert response.status_code == 302
    assert response.headers["Location"] == "/stats/validcode"


def test_handling_emoji_aliases(client, mocker):
    mocker.patch("blueprints.stats.validate_emoji_alias", return_value=True)
    mocker.patch(
        "blueprints.stats.load_emoji_url",
        return_value={"password": "correctpassword"},
    )
    response = client.post(
        "/stats", data={"short_code": "😀", "password": "correctpassword"}
    )
    assert response.status_code == 302
    assert (
        response.headers["Location"] == "/stats/%F0%9F%98%80?password=correctpassword"
    )


def test_stats_get_url_not_fount(client: FlaskClient, mocker):
    response = client.get("/stats/invalidcode")
    assert response.status_code == 404
    assert b"404, URL NOT FOUND" in response.data


def test_stats_post_url_not_fount(client):
    response = client.post("/stats/invalidcode")
    assert response.status_code == 404
    assert response.json == {"UrlError": "The requested Url never existed"}


def test_stats_get_password_protected_url_without_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url", return_value={"password": "correctpassword"}
    )
    response = client.get("/stats/validcode")
    assert response.status_code == 400
    assert (
        b"is a password protected Url, please enter the password to continue."
        in response.data
    )


def test_stats_get_password_protected_url_with_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url",
        return_value={
            "_id": "validcode",
            "url": "http://example.com",
            "password": "correctpassword",
            "creation-date": "2021-09-01",
        },
    )
    response = client.get("/stats/validcode?password=correctpassword")
    assert response.status_code == 200


def test_stats_get_password_protected_url_with_incorrect_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url", return_value={"password": "correctpassword"}
    )
    response = client.get("/stats/validcode?password=wrongpassword")
    assert response.status_code == 400
    assert (
        b"Invalid Password! please enter the correct password to continue."
        in response.data
    )


def test_stats_post_password_protected_without_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url", return_value={"password": "correctpassword"}
    )
    response = client.post("/stats/validcode")
    assert response.status_code == 400
    assert response.json == {"PasswordError": "Invalid Password"}


def test_stats_get_password_protected_correct_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url",
        return_value={
            "_id": "validcode",
            "url": "http://example.com",
            "password": "correctpassword",
            "creation-date": "2021-09-01",
        },
    )
    response = client.get("/stats/validcode?password=correctpassword")
    assert response.status_code == 200
    assert response.content_type == "text/html; charset=utf-8"


def test_stats_post_password_protected_correct_password(client, mocker):
    mocker.patch(
        "blueprints.stats.load_url",
        return_value={
            "_id": "validcode",
            "url": "http://example.com",
            "password": "correctpassword",
            "creation-date": "2021-09-01",
        },
    )
    response = client.post("/stats/validcode", data={"password": "correctpassword"})
    assert response.status_code == 200
    assert response.json == {
        "_id": "validcode",
        "average_daily_clicks": 0.0,
        "average_monthly_clicks": 0.0,
        "average_redirection_time": 0,
        "average_weekly_clicks": 0.0,
        "block-bots": False,
        "bots": {},
        "browser": {},
        "counter": {},
        "country": {},
        "creation-date": "2021-09-01",
        "expiration-time": None,
        "expired": None,
        "last-click-browser": None,
        "last-click-os": None,
        "max-clicks": None,
        "os_name": {},
        "password": "correctpassword",
        "referrer": {},
        "short_code": "validcode",
        "total-clicks": 0,
        "total_unique_clicks": 0,
        "unique_browser": {},
        "unique_country": {},
        "unique_os_name": {},
        "unique_referrer": {},
        "url": "http://example.com",
    }


def test_stats_get(client: FlaskClient, mocker):
    mocker.patch(
        "blueprints.stats.load_url",
        return_value={
            "_id": "validcode",
            "url": "http://example.com",
            "creation-date": "2021-09-01",
        },
    )
    response = client.get("/stats/validcode")
    assert response.status_code == 200
    assert response.content_type == "text/html; charset=utf-8"


def test_stats_post(client: FlaskClient, mocker):
    mocker.patch(
        "blueprints.stats.load_url",
        return_value={
            "_id": "validcode",
            "url": "http://example.com",
            "creation-date": "2021-09-01",
        },
    )
    response = client.post("/stats/validcode")
    assert response.status_code == 200
    assert response.json == {
        "_id": "validcode",
        "average_daily_clicks": 0.0,
        "average_monthly_clicks": 0.0,
        "average_redirection_time": 0,
        "average_weekly_clicks": 0.0,
        "block-bots": False,
        "bots": {},
        "browser": {},
        "counter": {},
        "country": {},
        "creation-date": "2021-09-01",
        "expiration-time": None,
        "expired": None,
        "last-click-browser": None,
        "last-click-os": None,
        "max-clicks": None,
        "os_name": {},
        "password": None,
        "referrer": {},
        "short_code": "validcode",
        "total-clicks": 0,
        "total_unique_clicks": 0,
        "unique_browser": {},
        "unique_country": {},
        "unique_os_name": {},
        "unique_referrer": {},
        "url": "http://example.com",
    }


def test_stats_post_expired_url_clicks(client: FlaskClient, mocker):
    mocker.patch(
        "blueprints.stats.load_url",
        return_value={
            "_id": "validcode",
            "url": "http://example.com",
            "creation-date": "2021-09-01",
            "total-clicks": 1,
            "total-unique-clicks": 1,
            "max-clicks": 1,
        },
    )
    response = client.post("/stats/validcode")
    assert response.status_code == 200
    assert response.json["expired"]


@pytest.mark.skip(reason="This feature is not implemented yet")
def test_stats_post_expired_url_time(client: FlaskClient, mocker):
    mocker.patch(
        "blueprints.stats.load_url",
        return_value={
            "_id": "validcode",
            "url": "http://example.com",
            "creation-date": "2021-09-01",
            "expiration-time": "2021-09-02",
        },
    )
    response = client.post("/stats/validcode")
    assert response.status_code == 200
    assert response.json["expired"]


@pytest.mark.parametrize(
    "db, short_code",
    [
        ("urls", "clicks"),
        ("emoji", "😀😄😭"),
    ],
)
def test_stats_post_after_clicks(client: FlaskClient, mocker, mock_db, db, short_code):
    today_str = str(datetime.today()).split()[0]

    mock_url_data = {
        "_id": short_code,
        "url": "https://example.com",
        "password": None,
        "total-clicks": 0,
        "ips": {},
        "referrer": {},
        "block-bots": False,
        "average_redirection_time": 0,
        "creation-date": today_str,
    }

    # Insert the mock data into the mock database
    mock_db[db].insert_one(mock_url_data)

    # Mock the database and other dependencies using mocker
    mocker.patch(
        f"utils.mongo_utils.{db if db == 'urls' else db + '_urls'}_collection",
        mock_db[db],
    )

    mocker.patch(
        "blueprints.url_shortener.get_client_ip",
        side_effect=["127.0.0.1", "127.0.0.1", "8.8.8.8"],
    )

    # Make requests to simulate clicks
    response = client.get(
        f"/{urllib.parse.quote(short_code)}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Referer": "https://www.example.com/page?query=123",
        },
    )
    assert response.status_code == 302

    response = client.get(
        f"/{urllib.parse.quote(short_code)}",
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
            "Referer": "https://mobile-site.co.uk/resource/page.html",
        },
    )
    assert response.status_code == 302

    response = client.get(
        f"/{urllib.parse.quote(short_code)}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "Referer": "https://www.example.com/page?query=123",
        },
    )
    assert response.status_code == 302

    # Post request to retrieve statistics
    response = client.post(f"/stats/{short_code}")
    assert response.status_code == 200
    assert response.is_json

    # Assertions for the response data
    assert response.json == {
        "_id": short_code,
        "average_daily_clicks": mocker.ANY,
        "average_monthly_clicks": round(3 / 30, 2),
        "average_redirection_time": mocker.ANY,
        "average_weekly_clicks": round(3 / 7, 2),
        "block-bots": False,
        "bots": {},
        "browser": {"Chrome": 2, "Safari": 1},
        "counter": {
            f"{today_str}": 3,
        },
        "country": {"United States": 1, "Unknown": 2},
        "creation-date": today_str,
        "expiration-time": None,
        "expired": None,
        "last-click": mocker.ANY,
        "last-click-browser": "Chrome",
        "last-click-country": "United States",
        "last-click-os": "Windows",
        "max-clicks": None,
        "os_name": {"Windows": 2, "Mac OS X": 1},
        "password": None,
        "referrer": {"example.com": 2, "mobile-site.co.uk": 1},
        "short_code": short_code,
        "total-clicks": 3,
        "total_unique_clicks": 2,
        "unique_browser": {"Chrome": 2, "Safari": 1},
        "unique_counter": {f"{today_str}": 2},
        "unique_country": {"United States": 1, "Unknown": 1},
        "unique_os_name": {"Windows": 2, "Mac OS X": 1},
        "unique_referrer": {"example.com": 2, "mobile-site.co.uk": 1},
        "url": "https://example.com",
    }


def test_stats_post_sorting_aggregation(client: FlaskClient, mocker, mock_db):
    short_code = "clicks"

    mock_url_data = {
        "_id": short_code,
        "url": "https://example.com",
        "average_redirection_time": 0,
        "average_daily_clicks": round(66 / 11, 2),
        "average_weekly_clicks": round(66 / 7, 2),
        "average_monthly_clicks": round(66 / 30, 2),
        "bots": {
            "Googlebot": 1,
            "BingBot": 2,
            "YandexBot": 3,
            "DuckDuckGo": 4,
            "Baidu": 2,
            "Unknown": 1,
            "PostmanRuntime": 5,
        },
        "browser": {
            "Chrome": {
                "ips": [
                    "0.0.0.0",
                    "1.1.1.1",
                    "2.2.2.2",
                    "3.3.3.3",
                    "4.4.4.4",
                    "5.5.5.5",
                ],
                "counts": 9,
            },
            "Safari": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2"],
                "counts": 6,
            },
            "Firefox": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"],
                "counts": 10,
            },
            "Chrome Mobile": {
                "ips": ["0.0.0.0", "1.1.1.1"],
                "counts": 8,
            },
            "Edge": {
                "ips": [
                    "0.0.0.0",
                    "1.1.1.1",
                    "2.2.2.2",
                    "3.3.3.3",
                    "4.4.4.4",
                    "5.5.5.5",
                    "6.6.6.6",
                ],
                "counts": 18,
            },
            "Edge Mobile": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"],
                "counts": 13,
            },
            "Unknown": {
                "ips": ["127.0.0.1"],
                "counts": 2,
            },
        },
        "country": {
            "United States": {
                "ips": [
                    "0.0.0.0",
                    "1.1.1.1",
                    "2.2.2.2",
                    "3.3.3.3",
                    "4.4.4.4",
                    "5.5.5.5",
                    "6.6.6.6",
                    "7.7.7.7",
                    "8.8.8.8",
                ],
                "counts": 25,
            },
            "United Kingdom": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2", "3.3.3.3"],
                "counts": 8,
            },
            "Japan": {
                "ips": [
                    "0.0.0.0",
                    "1.1.1.1",
                    "2.2.2.2",
                    "3.3.3.3",
                    "4.4.4.4",
                    "5.5.5.5",
                ],
                "counts": 10,
            },
            "France": {
                "ips": ["0.0.0.0", "1.1.1.1"],
                "counts": 5,
            },
            "Germany": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2"],
                "counts": 8,
            },
            "Romania": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2"],
                "counts": 7,
            },
            "Unknown": {
                "ips": ["127.0.0.1"],
                "counts": 3,
            },
        },
        "os_name": {
            "Windows": {
                "ips": [
                    "0.0.0.0",
                    "1.1.1.1",
                    "2.2.2.2",
                    "3.3.3.3",
                    "4.4.4.4",
                    "5.5.5.5",
                ],
                "counts": 12,
            },
            "Mac OS X": {
                "ips": [
                    "0.0.0.0",
                    "1.1.1.1",
                    "2.2.2.2",
                    "3.3.3.3",
                    "4.4.4.4",
                    "5.5.5.5",
                    "6.6.6.6",
                ],
                "counts": 22,
            },
            "Linux": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2", "3.3.3.3"],
                "counts": 5,
            },
            "Android": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"],
                "counts": 8,
            },
            "iOS": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2"],
                "counts": 7,
            },
            "Chrome OS": {
                "ips": ["0.0.0.0", "1.1.1.1", "2.2.2.2"],
                "counts": 10,
            },
            "Unknown": {
                "ips": ["127.0.0.1"],
                "counts": 2,
            },
        },
        "counter": {
            (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"): 14,
            (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d"): 2,
            (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"): 3,
            (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"): 4,
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 6,
            (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 7,
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 9,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 10,
            datetime.now().strftime("%Y-%m-%d"): 11,
        },
        "unique_counter": {
            (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"): 7,
            (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d"): 2,
            (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"): 2,
            (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"): 2,
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 6,
            (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 3,
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 3,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 2,
            datetime.now().strftime("%Y-%m-%d"): 2,
        },
        "total-clicks": 66,
        "password": None,
        "referrer": {
            "example.com": {
                "ips": ["0.0.0.0", "1.1.1.1"],
                "counts": 3,
            },
            "mobile-site.co.uk": {
                "ips": ["0.0.0.0"],
                "counts": 1,
            },
        },
        "ips": {},
        "last-click": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last-click-browser": "Chrome",
        "last-click-country": "United States",
        "last-click-os": "Windows",
        "block-bots": False,
        "creation-date": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
    }

    # Insert the mock data into the mock database
    mock_db.urls.insert_one(mock_url_data)

    # Mock the database and other dependencies using mocker
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)

    # Post request to retrieve statistics
    response = client.post(f"/stats/{short_code}")
    assert response.status_code == 200
    assert response.is_json

    assert response.json["counter"] == {
        (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"): 14,
        (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d"): 2,
        (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"): 3,
        (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"): 4,
        (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"): 0,
        (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 6,
        (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 7,
        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 0,
        (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 9,
        (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 10,
        datetime.now().strftime("%Y-%m-%d"): 11,
    }

    assert response.json["unique_counter"] == {
        (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"): 7,
        (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d"): 2,
        (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"): 2,
        (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"): 2,
        (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"): 0,
        (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 6,
        (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 3,
        (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 0,
        (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 3,
        (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 2,
        datetime.now().strftime("%Y-%m-%d"): 2,
    }

    assert response.json["browser"] == {
        "Chrome": 9,
        "Safari": 6,
        "Firefox": 10,
        "Chrome Mobile": 8,
        "Edge": 18,
        "Edge Mobile": 13,
        "Unknown": 2,
    }

    assert response.json["country"] == {
        "United States": 25,
        "United Kingdom": 8,
        "Japan": 10,
        "France": 5,
        "Germany": 8,
        "Romania": 7,
        "Unknown": 3,
    }

    assert response.json["os_name"] == {
        "Windows": 12,
        "Mac OS X": 22,
        "Linux": 5,
        "Android": 8,
        "iOS": 7,
        "Chrome OS": 10,
        "Unknown": 2,
    }

    assert response.json["referrer"] == {
        "example.com": 3,
        "mobile-site.co.uk": 1,
    }

    assert response.json["bots"] == {
        "Googlebot": 1,
        "BingBot": 2,
        "YandexBot": 3,
        "DuckDuckGo": 4,
        "Baidu": 2,
        "Unknown": 1,
        "PostmanRuntime": 5,
    }

    assert response.json["unique_browser"] == {
        "Chrome": 6,
        "Safari": 3,
        "Firefox": 5,
        "Chrome Mobile": 2,
        "Edge": 7,
        "Edge Mobile": 5,
        "Unknown": 1,
    }

    assert response.json["unique_country"] == {
        "United States": 9,
        "United Kingdom": 4,
        "Japan": 6,
        "France": 2,
        "Germany": 3,
        "Romania": 3,
        "Unknown": 1,
    }

    assert response.json["unique_os_name"] == {
        "Windows": 6,
        "Mac OS X": 7,
        "Linux": 4,
        "Android": 5,
        "iOS": 3,
        "Chrome OS": 3,
        "Unknown": 1,
    }

    assert response.json["unique_referrer"] == {
        "example.com": 2,
        "mobile-site.co.uk": 1,
    }
