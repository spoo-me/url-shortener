from utils.mongo_utils import validate_blocked_url


def test_url_not_blocked(mocker):
    # Mock the database call to return an empty list
    mocker.patch("utils.mongo_utils.blocked_urls_collection.find", return_value=[])
    assert validate_blocked_url("https://www.example.com")  # URL not blocked


def test_url_blocked(mocker):
    # Mock the database call to return a list with a blocked URL pattern
    mocker.patch(
        "utils.mongo_utils.blocked_urls_collection.find",
        return_value=[{"_id": "example.com"}],
    )
    assert not validate_blocked_url("https://www.example.com")  # URL is blocked


def test_url_partially_blocked(mocker):
    # Mock the database call to return a list with a blocked URL pattern
    mocker.patch(
        "utils.mongo_utils.blocked_urls_collection.find",
        return_value=[{"_id": "example"}],
    )
    assert not validate_blocked_url(
        "https://www.example.com"
    )  # URL is partially blocked


def test_url_with_no_match(mocker):
    # Mock the database call to return a list with a different blocked URL pattern
    mocker.patch(
        "utils.mongo_utils.blocked_urls_collection.find",
        return_value=[{"_id": "blocked.com"}],
    )
    assert validate_blocked_url(
        "https://www.example.com"
    )  # URL does not match blocked pattern


def test_url_with_regex_pattern(mocker):
    # Mock the database call to return a list with a regex pattern
    mocker.patch(
        "utils.mongo_utils.blocked_urls_collection.find",
        return_value=[{"_id": ".*example.*"}],
    )
    assert not validate_blocked_url(
        "https://www.example.com"
    )  # URL matches regex pattern
