import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta


def test_redirect_url_not_found(client, mocker, mock_db):
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)
    response = client.get("/nonexistent")
    assert response.status_code == 404
    assert b"URL NOT FOUND" in response.data


def test_redirect_url_emoji_not_found(client, mocker, mock_db):
    mocker.patch("utils.mongo_utils.emoji_urls_collection", mock_db.emojis)
    response = client.get("/%F0%9F%98%80")
    assert response.status_code == 404
    assert b"URL NOT FOUND" in response.data


def test_redirect_url_expired(client, mocker, mock_db):
    mock_url_data = {
        "_id": "expired",
        "url": "http://example.com",
        "max-clicks": 10,
        "total-clicks": 10,
    }

    mock_db.urls.insert_one(mock_url_data)
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)

    response = client.get("/expired")
    assert response.status_code == 400
    assert b"SHORT URL EXPIRED" in response.data


def test_redirect_url_password_protected(client, mocker, mock_db):
    mock_url_data = {
        "_id": "protected",
        "url": "http://example.com",
        "password": "secret",
    }

    mock_db.urls.insert_one(mock_url_data)
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)

    response = client.get("/protected")
    assert response.status_code == 401
    assert b"Enter the password" in response.data


def test_redirect_url_success(client, mocker, mock_db):
    mock_url_data = {
        "_id": "valid",
        "url": "http://example.com",
        "total-clicks": 0,
        "ips": {},
        "referrer": {},
        "block-bots": False,
        "average_redirection_time": 0,
    }

    mock_db.urls.insert_one(mock_url_data)
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)

    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")
    mocker.patch(
        "blueprints.url_shortener.parse",
        return_value=MagicMock(
            os=MagicMock(family="Windows"), browser=MagicMock(family="Chrome")
        ),
    )
    mocker.patch(
        "blueprints.url_shortener.crawler_detect.isCrawler", return_value=False
    )

    response = client.get("/valid")
    assert response.status_code == 302
    assert response.headers["Location"] == "http://example.com"


def test_redirect_url_emoji(client, mocker, mock_db):
    mock_url_data = {
        "_id": "😀",
        "url": "http://example.com",
        "total-clicks": 0,
        "ips": {},
        "referrer": {},
        "block-bots": False,
        "average_redirection_time": 0,
    }

    mock_db.emojis.insert_one(mock_url_data)
    mocker.patch("utils.mongo_utils.emoji_urls_collection", mock_db.emojis)

    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")
    mocker.patch(
        "blueprints.url_shortener.parse",
        return_value=MagicMock(
            os=MagicMock(family="Windows"), browser=MagicMock(family="Chrome")
        ),
    )
    mocker.patch(
        "blueprints.url_shortener.crawler_detect.isCrawler", return_value=False
    )

    response = client.get("/%F0%9F%98%80")
    assert response.status_code == 302
    assert response.headers["Location"] == "http://example.com"


@pytest.mark.parametrize(
    "user_agent",
    [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",  # Google bot
        "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)",  # Bing bot
        "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",  # Yahoo bot
        "DuckDuckBot/1.0; (+http://duckduckgo.com/duckduckbot.html)",  # DuckDuckGo bot
        "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",  # Baidu bot
        "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",  # Yandex bot
        "Sogou web spider/4.0 (+http://www.sogou.com/docs/help/webmasters.htm#07)",  # Sogou bot
        "Mozilla/5.0 (compatible; Exabot/3.0; +http://www.exabot.com/go/robot)",  # Exalead bot
        "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",  # Facebook bot
        "ia_archiver (+http://www.alexa.com/site/help/webmasters; crawler@alexa.com)",  # Alexa bot
    ],
)
def test_redirect_url_block_bots(client, mocker, mock_db, user_agent):
    mock_url_data = {
        "_id": "botblocked",
        "url": "http://example.com",
        "block-bots": True,
        "total-clicks": 0,
    }

    mock_db.urls.insert_one(mock_url_data)
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)

    response = client.get("/botblocked", headers={"User-Agent": user_agent})
    assert response.status_code == 403
    assert b"Bots not allowed" in response.data


def test_redirect_url_click_limit_exceeded(client, mocker, mock_db):
    mock_url_data = {
        "_id": "limit",
        "url": "http://example.com",
        "max-clicks": 5,
        "total-clicks": 5,
    }

    mock_db.urls.insert_one(mock_url_data)
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)

    response = client.get("/limit")
    assert response.status_code == 400
    assert b"SHORT URL EXPIRED" in response.data


@pytest.mark.skip(reason="Feature not yet implemented")
def test_redirect_url_expired_time(client, mocker, mock_db):
    mock_url_data = {
        "_id": "expiredtime",
        "url": "http://example.com",
        "expiration-time": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    }

    mock_db.urls.insert_one(mock_url_data)
    mocker.patch("utils.mongo_utils.urls_collection", mock_db.urls)

    response = client.get("/expiredtime")
    assert response.status_code == 400
    assert b"SHORT CODE EXPIRED" in response.data


def test_redirect_url_redirection_time_update(client, mocker, mock_db):
    mocker.patch(
        "blueprints.url_shortener.load_url",
        return_value={
            "_id": "redirectiontime",
            "url": "http://example.com",
            "average_redirection_time": 100,
        },
    )
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")
    mocker.patch(
        "blueprints.url_shortener.parse",
        return_value=MagicMock(
            os=MagicMock(family="Windows"), browser=MagicMock(family="Chrome")
        ),
    )
    mock_update_url = mocker.patch("blueprints.url_shortener.update_url")

    response = client.get("/redirectiontime")
    assert response.status_code == 302
    assert mock_update_url.called


@pytest.mark.parametrize(
    "user_agent, ip_address, referrer, expected_browser, expected_os, expected_country, expected_referrer",
    [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            "8.8.8.8",
            "https://www.example.com/page?query=123",
            "Chrome",
            "Windows",
            "United States",
            "example.com",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
            "110.33.122.75",
            "https://sub.domain.com/path/to/resource",
            "Safari",
            "Mac OS X",
            "Australia",
            "domain.com",
        ),
        (
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "101.96.32.0",
            "http://another-example.org/page?foo=bar",
            "Firefox",
            "Ubuntu",
            "Japan",
            "another-example.org",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
            "192.206.151.131",
            "https://mobile-site.co.uk/resource/page.html",
            "Mobile Safari",
            "iOS",
            "Canada",
            "mobile-site.co.uk",
        ),
        (
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.105 Mobile Safari/537.36",
            "85.214.132.117",
            "https://app.android.com/path/to/file?param=value",
            "Chrome Mobile",
            "Android",
            "Germany",
            "android.com",
        ),
    ],
)
def test_redirection_db_update_clicks(
    client,
    mocker,
    mock_db,
    user_agent,
    ip_address,
    referrer,
    expected_browser,
    expected_os,
    expected_country,
    expected_referrer,
):
    mocker.patch(
        "blueprints.url_shortener.load_url",
        return_value={
            "_id": "clicks",
            "url": "http://example.com",
            "total-clicks": 0,
            "ips": {},
            "referrer": {},
            "block-bots": False,
            "average_redirection_time": 0,
        },
    )
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value=ip_address)
    mock_update_url = mocker.patch("blueprints.url_shortener.update_url")

    response = client.get(
        "/clicks", headers={"User-Agent": user_agent, "Referer": referrer}
    )
    assert response.status_code == 302

    today_str = str(datetime.today()).split()[0]

    updates = mock_update_url.call_args[0][1]
    assert updates == {
        "$inc": {
            "total-clicks": 1,
            f"browser.{expected_browser}.counts": 1,
            f"os_name.{expected_os}.counts": 1,
            f"counter.{today_str}": 1,
            f"country.{expected_country}.counts": 1,
            f"unique_counter.{today_str}": 1,
        },
        "$set": {
            "last-click": mocker.ANY,
            "last-click-browser": expected_browser,
            "last-click-os": expected_os,
            "last-click-country": expected_country,
            "ips": {
                ip_address: 1,
            },
            "average_redirection_time": mocker.ANY,
            "referrer": {
                f"{expected_referrer}": {
                    "counts": 1,
                    "ips": [ip_address],
                }
            },
        },
        "$addToSet": {
            f"browser.{expected_browser}.ips": ip_address,
            f"os_name.{expected_os}.ips": ip_address,
            f"country.{expected_country}.ips": ip_address,
        },
    }


@pytest.mark.parametrize(
    "user_agent, bot_name",
    [
        (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "GoogleBot",
        ),
        (
            "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)",
            "BingBot",
        ),
        (
            "Mozilla/5.0 (compatible; Yahoo! Slurp; http://help.yahoo.com/help/us/ysearch/slurp)",
            "Slurp",
        ),
        ("DuckDuckBot/1.0; (+http://duckduckgo.com/duckduckbot.html)", "DuckDuckBot"),
        (
            "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
            "Baidu",
        ),
        (
            "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
            "YandexBot",
        ),
        (
            "Sogou web spider/4.0 (+http://www.sogou.com/docs/help/webmasters.htm#07)",
            "Sogou",
        ),
        (
            "Mozilla/5.0 (compatible; Exabot/3.0; +http://www.exabot.com/go/robot)",
            "Exabot",
        ),
    ],
)
def test_redirection_db_update_bot(client, mocker, user_agent, bot_name):
    mocker.patch(
        "blueprints.url_shortener.load_url",
        return_value={
            "_id": "bot",
            "url": "http://example.com",
            "total-clicks": 0,
            "ips": {},
            "referrer": {},
            "block-bots": False,
            "average_redirection_time": 0,
        },
    )
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")
    mocker.patch(
        "blueprints.url_shortener.parse",
        return_value=MagicMock(
            os=MagicMock(family="Windows"), browser=MagicMock(family="Chrome")
        ),
    )
    mock_update_url = mocker.patch("blueprints.url_shortener.update_url")

    headers = {"User-Agent": user_agent}
    response = client.get("/bot", headers=headers)
    assert response.status_code == 302

    updates = mock_update_url.call_args[0][1]
    assert f"bots.{bot_name}" in updates["$inc"]
    assert updates["$inc"][f"bots.{bot_name}"] == 1


def test_multiple_clicks_same_ip_db_update(client, mocker, mock_db):
    mocker.patch(
        "blueprints.url_shortener.load_url",
        return_value={
            "_id": "multiple",
            "url": "http://example.com",
            "total-clicks": 0,
            "ips": {},
            "referrer": {},
            "block-bots": False,
            "average_redirection_time": 0,
        },
    )

    # Mock the client IP and user agent for two separate clicks
    mocker.patch(
        "blueprints.url_shortener.get_client_ip", side_effect=["127.0.0.1", "127.0.0.1"]
    )
    mocker.patch(
        "blueprints.url_shortener.parse",
        return_value=MagicMock(
            os=MagicMock(family="Windows"), browser=MagicMock(family="Chrome")
        ),
    )
    mock_update_url = mocker.patch("blueprints.url_shortener.update_url")

    # Simulate first click
    response1 = client.get("/multiple", headers={"User-Agent": "Mozilla/5.0"})
    assert response1.status_code == 302

    today_str = str(datetime.today()).split()[0]

    # Simulate second click
    response2 = client.get("/multiple", headers={"User-Agent": "Mozilla/5.0"})
    assert response2.status_code == 302

    updates_first_click = mock_update_url.call_args_list[0][0][1]

    assert updates_first_click == {
        "$inc": {
            "total-clicks": 1,
            f"counter.{today_str}": 1,
            f"unique_counter.{today_str}": 1,  # First click is unique
            "browser.Chrome.counts": 1,
            "os_name.Windows.counts": 1,
            "country.Unknown.counts": 1,
        },
        "$set": {
            "last-click": mocker.ANY,
            "last-click-browser": "Chrome",
            "last-click-os": "Windows",
            "last-click-country": "Unknown",
            "ips": {
                "127.0.0.1": 1,
            },
            "average_redirection_time": mocker.ANY,
        },
        "$addToSet": {
            "browser.Chrome.ips": "127.0.0.1",
            "country.Unknown.ips": "127.0.0.1",
            "os_name.Windows.ips": "127.0.0.1",
        },
    }

    # Assert the second update call
    mock_db["urls"].update_one.assert_any_call(
        {"_id": "multiple"},
        {
            "$inc": {
                "total-clicks": 1,
                f"counter.{today_str}": 1,
                # unique counter is not added because the second click is not unique
                "browser.Chrome.counts": 1,
                "os_name.Windows.counts": 1,
                "country.Unknown.counts": 1,
            },
            "$set": {
                "last-click": mocker.ANY,
                "last-click-browser": "Chrome",
                "last-click-os": "Windows",
                "last-click-country": "Unknown",
                "ips": {
                    "127.0.0.1": 2,
                },
                "average_redirection_time": mocker.ANY,
            },
            "$addToSet": {
                "browser.Chrome.ips": "127.0.0.1",
                "country.Unknown.ips": "127.0.0.1",
                "os_name.Windows.ips": "127.0.0.1",
            },
        },
    )

    # Ensure update_one was called exactly twice
    assert mock_db["urls"].update_one.call_count == 2


def test_multiple_clicks_different_ip_db_update(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "multiple",
        "url": "http://example.com",
        "total-clicks": 0,
        "ips": {},
        "referrer": {},
        "block-bots": False,
        "average_redirection_time": 0,
    }

    # Mock the client IP and user agent for two separate clicks
    mocker.patch(
        "blueprints.url_shortener.get_client_ip", side_effect=["127.0.0.1", "8.8.8.8"]
    )

    # Simulate first click
    response1 = client.get(
        "/multiple",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        },
    )
    assert response1.status_code == 302

    # Simulate second click
    response2 = client.get(
        "/multiple",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        },
    )
    assert response2.status_code == 302

    today_str = str(datetime.today()).split()[0]

    # Assert the second update call
    mock_db["urls"].update_one.assert_any_call(
        {"_id": "multiple"},
        {
            "$inc": {
                "total-clicks": 1,
                f"counter.{today_str}": 1,
                f"unique_counter.{today_str}": 1,  # Second click is unique
                "browser.Chrome.counts": 1,
                "os_name.Windows.counts": 1,
                "country.United States.counts": 1,
            },
            "$set": {
                "last-click": mocker.ANY,
                "last-click-browser": "Chrome",
                "last-click-os": "Windows",
                "last-click-country": "United States",
                "ips": {
                    "127.0.0.1": 1,
                    "8.8.8.8": 1,
                },
                "average_redirection_time": mocker.ANY,
            },
            "$addToSet": {
                "browser.Chrome.ips": "8.8.8.8",
                "country.United States.ips": "8.8.8.8",
                "os_name.Windows.ips": "8.8.8.8",
            },
        },
    )

    # Ensure update_one was called exactly twice
    assert mock_db["urls"].update_one.call_count == 2


def test_multiple_clicks_same_referrer_db_update(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "multiple",
        "url": "http://example.com",
        "total-clicks": 0,
        "ips": {},
        "referrer": {},
        "block-bots": False,
        "average_redirection_time": 0,
    }

    # Mock the client IP and user agent for two separate clicks
    mocker.patch(
        "blueprints.url_shortener.get_client_ip", side_effect=["127.0.0.1", "8.8.8.8"]
    )
    mocker.patch(
        "blueprints.url_shortener.parse",
        return_value=MagicMock(
            os=MagicMock(family="Windows"), browser=MagicMock(family="Chrome")
        ),
    )

    # Simulate first click
    response = client.get(
        "/multiple", headers={"Referer": "https://www.example.com/page?query=123"}
    )
    assert response.status_code == 302

    # Simulate second click
    response = client.get(
        "/multiple", headers={"Referer": "https://www.example.com/page?query=123"}
    )

    assert response.status_code == 302

    today_str = str(datetime.today()).split()[0]

    # Assert the second update call
    mock_db["urls"].update_one.assert_any_call(
        {"_id": "multiple"},
        {
            "$inc": {
                "total-clicks": 1,
                f"counter.{today_str}": 1,
                f"unique_counter.{today_str}": 1,  # Second click is unique
                "browser.Chrome.counts": 1,
                "os_name.Windows.counts": 1,
                "country.United States.counts": 1,
            },
            "$set": {
                "last-click": mocker.ANY,
                "last-click-browser": "Chrome",
                "last-click-os": "Windows",
                "last-click-country": "United States",
                "ips": {
                    "127.0.0.1": 1,
                    "8.8.8.8": 1,
                },
                "average_redirection_time": mocker.ANY,
                "referrer": {
                    "example.com": {
                        "counts": 2,
                        "ips": ["127.0.0.1", "8.8.8.8"],
                    }
                },
            },
            "$addToSet": {
                "browser.Chrome.ips": "8.8.8.8",
                "country.United States.ips": "8.8.8.8",
                "os_name.Windows.ips": "8.8.8.8",
            },
        },
    )

    assert mock_db["urls"].update_one.call_count == 2


def test_multiple_clicks_different_referrer_db_update(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "multiple",
        "url": "http://example.com",
        "total-clicks": 0,
        "ips": {},
        "referrer": {},
        "block-bots": False,
        "average_redirection_time": 0,
    }

    # Mock the client IP and user agent for two separate clicks
    mocker.patch(
        "blueprints.url_shortener.get_client_ip", side_effect=["127.0.0.1", "8.8.8.8"]
    )
    mocker.patch(
        "blueprints.url_shortener.parse",
        return_value=MagicMock(
            os=MagicMock(family="Windows"), browser=MagicMock(family="Chrome")
        ),
    )

    # Simulate first click
    response = client.get(
        "/multiple", headers={"Referer": "https://www.example.com/page?query=123"}
    )
    assert response.status_code == 302

    # Simulate second click
    response = client.get(
        "/multiple", headers={"Referer": "https://sub.domain.com/path/to/resource"}
    )
    assert response.status_code == 302

    today_str = str(datetime.today()).split()[0]

    # Assert the second update call

    mock_db["urls"].update_one.assert_any_call(
        {"_id": "multiple"},
        {
            "$inc": {
                "total-clicks": 1,
                f"counter.{today_str}": 1,
                f"unique_counter.{today_str}": 1,  # Second click is unique
                "browser.Chrome.counts": 1,
                "os_name.Windows.counts": 1,
                "country.United States.counts": 1,
            },
            "$set": {
                "last-click": mocker.ANY,
                "last-click-browser": "Chrome",
                "last-click-os": "Windows",
                "last-click-country": "United States",
                "ips": {
                    "127.0.0.1": 1,
                    "8.8.8.8": 1,
                },
                "average_redirection_time": mocker.ANY,
                "referrer": {
                    "example.com": {
                        "counts": 1,
                        "ips": ["127.0.0.1"],
                    },
                    "domain.com": {
                        "counts": 1,
                        "ips": ["8.8.8.8"],
                    },
                },
            },
            "$addToSet": {
                "browser.Chrome.ips": "8.8.8.8",
                "country.United States.ips": "8.8.8.8",
                "os_name.Windows.ips": "8.8.8.8",
            },
        },
    )

    assert mock_db["urls"].update_one.call_count == 2


def test_valid_password(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "validcode",
        "password": "correctpassword",
    }
    response = client.post("/validcode/password", data={"password": "correctpassword"})
    assert response.status_code == 302
    assert (
        response.headers["Location"]
        == "http://localhost/validcode?password=correctpassword"
    )


def test_invalid_password(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "validcode",
        "password": "correctpassword",
    }
    response = client.post("/validcode/password", data={"password": "wrongpassword"})
    assert response.status_code == 200
    assert b"Incorrect Password" in response.data


def test_url_without_password(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "nopasswordcode",
    }
    response = client.post("/nopasswordcode/password", data={"password": "any"})
    assert response.status_code == 400
    assert b"Invalid short code or URL not password-protected" in response.data


def test_short_code_not_found(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = None
    response = client.post("/nonexistentcode/password", data={"password": "any"})
    assert response.status_code == 400
    assert b"Invalid short code or URL not password-protected" in response.data


def test_missing_password_field(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "validcode",
        "password": "correctpassword",
    }
    response = client.post("/validcode/password", data={})
    assert response.status_code == 200
    assert b"Incorrect Password" in response.data


def test_emoji_based_url(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["emojis"].find_one.return_value = {
        "_id": "😀",
        "password": "correctpassword",
    }
    response = client.post(
        "/%F0%9F%98%80/password", data={"password": "correctpassword"}
    )
    assert response.status_code == 302
    assert (
        response.headers["Location"]
        == "http://localhost/%F0%9F%98%80?password=correctpassword"
    )


def test_redirection_url_validation(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = {
        "_id": "validcode",
        "password": "correctpassword",
    }
    response = client.post("/validcode/password", data={"password": "correctpassword"})
    assert response.status_code == 302
    assert (
        response.headers["Location"]
        == "http://localhost/validcode?password=correctpassword"
    )


@pytest.mark.xfail(reason="Flask Cache is causing issues with the test")
@pytest.mark.parametrize(
    "total_clicks, total_shortlinks, expected_result",
    [
        (0, 0, {"total-clicks": "0", "total-shortlinks": "0"}),
        (12345, 6789, {"total-clicks": "12K+", "total-shortlinks": "6K+"}),
        (1234567, 67890, {"total-clicks": "1M+", "total-shortlinks": "68K+"}),
    ],
)
def test_metric(client, mocker, total_clicks, total_shortlinks, expected_result):
    # Mock the cache.get method to simulate a cache miss
    mock_cache = mocker.patch("blueprints.url_shortener.cache")
    mock_cache.get.return_value = None  # Simulate cache miss

    # Mock the MongoDB collection aggregate method to return a specific result
    mock_collection = mocker.patch("blueprints.url_shortener.collection")
    mock_collection.aggregate.return_value.next.return_value = {
        "_id": "some_id",
        "total-clicks": total_clicks,
        "total-shortlinks": total_shortlinks,
    }

    # Mock the cache.set method to ensure it can be called without issues
    mock_cache.set.return_value = None

    response = client.get("/metric")
    assert response.status_code == 200

    expected_result = {
        "total-clicks": expected_result["total-clicks"],
        "total-shortlinks": expected_result["total-shortlinks"],
    }
    assert response.json == expected_result
