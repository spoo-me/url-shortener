import pytest
from flask import Flask
from blueprints.url_shortener import url_shortener
from unittest.mock import MagicMock
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


@pytest.fixture
def client():
    app = Flask(__name__)
    app.register_blueprint(url_shortener)
    app.config["TESTING"] = True
    app.config["RATELIMIT_HEADERS_ENABLED"] = True

    # Initialize the rate limiter
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["2 per minute", "500 per day", "50 per hour"],
        storage_uri="memory://",
        strategy="fixed-window",
    )
    limiter.init_app(app)

    with app.test_client() as client:
        yield client


def test_rate_limiter(client, mocker):
    mock_db = mocker.patch("blueprints.url_shortener.db")
    mock_db["urls"].find_one.return_value = None
    mocker.patch("blueprints.url_shortener.validate_url", return_value=True)
    mocker.patch("blueprints.url_shortener.check_if_slug_exists", return_value=False)
    mocker.patch(
        "blueprints.url_shortener.generate_short_code", return_value="shortcode"
    )
    mocker.patch("blueprints.url_shortener.add_url_by_id")

    for _ in range(2):
        response = client.post(
            "/",
            data={"url": "http://example.com"},
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 200

    # The 6th request should be rate limited
    response = client.post(
        "/", data={"url": "http://example.com"}, headers={"Accept": "application/json"}
    )
    assert response.status_code == 429
    assert b"Too Many Requests" in response.data


if __name__ == "__main__":
    pytest.main()
