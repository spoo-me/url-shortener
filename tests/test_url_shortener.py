import pytest
import json
from flask import Flask
from blueprints.url_shortener import url_shortener
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


def test_index_no_cookies(client):
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.xfail()
def test_index_with_cookies(client):
    recent_urls = ["http://example.com/1", "http://example.com/2"]
    serialized_list = json.dumps(recent_urls)
    response = client.get("/", headers={"Cookie": f"shortURL={serialized_list}"})
    assert response.status_code == 200
    for url in recent_urls:
        assert url.encode() in response.data


def test_shorten_url_no_url(client):
    response = client.post("/", data={})
    assert response.status_code == 400
    assert b"URL is required" in response.data


def test_shorten_url_invalid_url(client):
    response = client.post("/", data={"url": "invalid-url"})
    assert response.status_code == 400
    assert b"Invalid URL" in response.data


def test_shorten_url_blocked_url(client, mocker):
    mocker.patch("blueprints.url_shortener.validate_blocked_url", return_value=False)
    response = client.post("/", data={"url": "http://blocked-url.com"})
    assert response.status_code == 403
    assert b"Blocked URL" in response.data


@pytest.mark.parametrize(
    "invalid_alias",
    [
        "invalid alias",  # Space in alias
        "invalid@alias",  # Special character
        "emoji😀alias",  # Emoji in alias
        "alias!",  # Exclamation mark
        "alias#",  # Hash symbol
        "alias$",  # Dollar sign
        "alias%",  # Percent sign
        "alias^",  # Caret
        "alias&",  # Ampersand
        "alias*",  # Asterisk
        "alias(",  # Open parenthesis
        "alias)",  # Close parenthesis
        "alias+",  # Plus sign
        "alias=",  # Equals sign
        "alias{",  # Open curly brace
        "alias}",  # Close curly brace
        "alias[",  # Open square bracket
        "alias]",  # Close square bracket
        "alias|",  # Vertical bar
        "alias\\",  # Backslash
        "alias/",  # Forward slash
        "alias:",  # Colon
        "alias;",  # Semicolon
        "alias'",  # Single quote
        'alias"',  # Double quote
        "alias<",  # Less than
        "alias>",  # Greater than
        "alias,",  # Comma
        "alias.",  # Period
        "alias?",  # Question mark
        "alias~",  # Tilde
        "alias`",  # Backtick
    ],
)
def test_shorten_url_invalid_alias(client, invalid_alias):
    response = client.post(
        "/", data={"url": "http://example.com", "alias": invalid_alias}
    )
    assert response.status_code == 400
    assert b"Invalid Alias" in response.data


def test_shorten_url_alias_exists(client, mocker):
    mocker.patch("blueprints.url_shortener.check_if_slug_exists", return_value=True)
    response = client.post(
        "/", data={"url": "http://example.com", "alias": "existingalias"}
    )
    assert response.status_code == 400
    assert b"Alias already exists" in response.data


def test_shorten_url_invalid_password(client):
    response = client.post("/", data={"url": "http://example.com", "password": "short"})
    assert response.status_code == 400
    assert b"Invalid password" in response.data


def test_shorten_url_invalid_max_clicks(client):
    response = client.post("/", data={"url": "http://example.com", "max-clicks": "-10"})
    assert response.status_code == 400
    assert b"max-clicks must be an positive integer" in response.data


@pytest.mark.skip(reason="Feature not implemented yet")
def test_shorten_url_invalid_expiration_time(client):
    response = client.post(
        "/", data={"url": "http://example.com", "expiration-time": "invalid-time"}
    )
    assert response.status_code == 400
    assert b"Invalid expiration-time" in response.data


def test_shorten_url_success(client, mocker):
    mocker.patch("blueprints.url_shortener.check_if_slug_exists", return_value=False)
    mocker.patch("blueprints.url_shortener.generate_short_code", return_value="abc123")
    mocker.patch("blueprints.url_shortener.add_url_by_id")
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")

    response = client.post("/", data={"url": "http://example.com"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/result/abc123")


def test_shorten_url_success_max_clicks(client, mocker):
    mocker.patch("blueprints.url_shortener.check_if_slug_exists", return_value=False)
    mocker.patch("blueprints.url_shortener.generate_short_code", return_value="abc123")
    mocker.patch("blueprints.url_shortener.add_url_by_id")
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")

    response = client.post("/", data={"url": "http://example.com", "max-clicks": "10"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/result/abc123")


def test_shorten_url_success_password(client, mocker):
    mocker.patch("blueprints.url_shortener.check_if_slug_exists", return_value=False)
    mocker.patch("blueprints.url_shortener.generate_short_code", return_value="abc123")
    mocker.patch("blueprints.url_shortener.add_url_by_id")
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")

    response = client.post(
        "/", data={"url": "http://example.com", "password": "Strong@password12"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/result/abc123")


def test_shorten_url_ratelimiting(client, mocker):
    mocker.patch("blueprints.url_shortener.check_if_slug_exists", return_value=False)
    mocker.patch("blueprints.url_shortener.generate_short_code", return_value="abc123")
    mocker.patch("blueprints.url_shortener.add_url_by_id")
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")


@pytest.mark.skip(reason="Feature not implemented yet")
def test_shorten_url_success_expiration_time(client, mocker):
    mocker.patch("blueprints.url_shortener.check_if_slug_exists", return_value=False)
    mocker.patch("blueprints.url_shortener.generate_short_code", return_value="abc123")
    mocker.patch("blueprints.url_shortener.add_url_by_id")
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")

    response = client.post(
        "/", data={"url": "http://example.com", "expiration-time": "1"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/result/abc123")


def test_emoji_no_url(client):
    response = client.post("/emoji", data={})
    assert response.status_code == 400
    assert b"URL is required" in response.data


def test_emoji_invalid_url(client):
    response = client.post("/emoji", data={"url": "invalid-url"})
    assert response.status_code == 400
    assert b"Invalid URL" in response.data


def test_emoji_blocked_url(client, mocker):
    mocker.patch("blueprints.url_shortener.validate_blocked_url", return_value=False)
    response = client.post("/emoji", data={"url": "http://blocked-url.com"})
    assert response.status_code == 403
    assert b"Blocked URL" in response.data


def test_emoji_invalid_emoji(client):
    response = client.post(
        "/emoji", data={"url": "http://example.com", "emojies": "invalid-emoji"}
    )
    assert response.status_code == 400
    assert b"Invalid emoji" in response.data


def test_emoji_emoji_exists(client, mocker):
    mocker.patch(
        "blueprints.url_shortener.check_if_emoji_alias_exists", return_value=True
    )
    response = client.post(
        "/emoji", data={"url": "http://example.com", "emojies": "🤯"}
    )
    assert response.status_code == 400
    assert b"Emoji already exists" in response.data


def test_emoji_invalid_password(client):
    response = client.post(
        "/emoji", data={"url": "http://example.com", "password": "short"}
    )
    assert response.status_code == 400
    assert b"Invalid password" in response.data


def test_emoji_invalid_max_clicks(client):
    response = client.post(
        "/emoji", data={"url": "http://example.com", "max-clicks": "-10"}
    )
    assert response.status_code == 400
    assert b"max-clicks must be an positive integer" in response.data


def test_emoji_invalid_expiration_time(client):
    response = client.post(
        "/emoji", data={"url": "http://example.com", "expiration-time": "invalid-time"}
    )
    assert response.status_code == 400
    assert b"Invalid expiration-time" in response.data


def test_emoji_success(client, mocker):
    mocker.patch(
        "blueprints.url_shortener.check_if_emoji_alias_exists", return_value=False
    )
    mocker.patch("blueprints.url_shortener.generate_emoji_alias", return_value="😀")
    mocker.patch("blueprints.url_shortener.add_emoji_by_alias")
    mocker.patch("blueprints.url_shortener.get_client_ip", return_value="127.0.0.1")

    response = client.post("/emoji", data={"url": "http://example.com"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        "/result/%F0%9F%98%80"
    )  # %F0%9F%98%80 is the url encoded version of 😀


def test_result_valid_short_code(client, mocker):
    mocker.patch("blueprints.url_shortener.validate_emoji_alias", return_value=False)
    mocker.patch(
        "blueprints.url_shortener.load_url_by_id", return_value={"_id": "abc123"}
    )

    response = client.get("/result/abc123")
    assert response.status_code == 200
    assert b"http://localhost/abc123" in response.data


def test_result_valid_emoji_alias(client, mocker):
    mocker.patch("blueprints.url_shortener.validate_emoji_alias", return_value=True)
    mocker.patch(
        "blueprints.url_shortener.load_emoji_by_alias",
        return_value={"_id": "%F0%9F%98%80"},
    )

    response = client.get("/result/%F0%9F%98%80")
    assert response.status_code == 200
    assert b"http://localhost/%F0%9F%98%80" in response.data


def test_result_invalid_short_code(client, mocker):
    mocker.patch("blueprints.url_shortener.validate_emoji_alias", return_value=False)
    mocker.patch("blueprints.url_shortener.load_url_by_id", return_value=None)

    response = client.get("/result/invalid")
    assert response.status_code == 404
    assert b"URL NOT FOUND" in response.data


def test_result_invalid_emoji_alias(client, mocker):
    mocker.patch("blueprints.url_shortener.validate_emoji_alias", return_value=True)
    mocker.patch("blueprints.url_shortener.load_emoji_by_alias", return_value=None)

    response = client.get("/result/%F0%9F%98%80")
    assert response.status_code == 404
    assert b"URL NOT FOUND" in response.data
