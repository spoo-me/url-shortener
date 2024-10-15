import pytest
from utils import get_country, get_client_ip, humanize_number, is_positive_integer, convert_country_name, generate_short_code, generate_passkey, validate_string, add_missing_dates, top_four, calculate_click_averages,validate_emoji_alias
from flask import Flask
import string
from datetime import datetime, timedelta
from urllib.parse import unquote
import emoji

app = Flask(__name__)

def test_get_country():
    ip_address = "8.8.8.8"  # Example IP address
    country = get_country(ip_address)
    assert country == "United States"

def test_get_unknown_country():
    ip_address = "127.0.0.1"  # Localhost IP address
    country = get_country(ip_address)
    assert country == "Unknown"

# Retrieves IP from HTTP_X_FORWARDED_FOR if present
def test_retrieves_ip_from_http_x_forwarded_for(mocker):
    with app.test_request_context(environ_base={'HTTP_X_FORWARDED_FOR': '192.168.1.1, 10.0.0.1'}):
        ip = get_client_ip()
        assert ip == "192.168.1.1"

# Handles empty HTTP_X_FORWARDED_FOR header gracefully
def test_handles_empty_http_x_forwarded_for(mocker):
    with app.test_request_context(environ_base={'HTTP_X_FORWARDED_FOR': ''}):
        ip = get_client_ip()
        assert ip == ""

# Test humanize_number

def test_humanize_number_small():
    assert humanize_number(999) == "999+"

def test_humanize_number_thousands():
    assert humanize_number(1000) == "1K+"
    assert humanize_number(1500) == "1K+"
    assert humanize_number(999999) == "999K+"

def test_humanize_number_millions():
    assert humanize_number(1000000) == "1M+"
    assert humanize_number(1500000) == "1M+"
    assert humanize_number(999999999) == "999M+"

def test_humanize_number_billions():
    assert humanize_number(1000000000) == "1B+"
    assert humanize_number(1500000000) == "1B+"
    assert humanize_number(999999999999) == "999B+"

def test_humanize_number_trillions():
    assert humanize_number(1000000000000) == "1T+"
    assert humanize_number(1500000000000) == "1T+"
    assert humanize_number(999999999999999) == "999T+"

def test_humanize_number_negative():
    assert humanize_number(-1000) == "-1K+"
    assert humanize_number(-1500000) == "-1M+"

def test_humanize_number_zero():
    assert humanize_number(0) == "0+"

# Test positive integer

def test_is_positive_integer_with_positive_integer():
    assert is_positive_integer(5) == True

def test_is_positive_integer_with_zero():
    assert is_positive_integer(0) == True

def test_is_positive_integer_with_negative_integer():
    assert is_positive_integer(-5) == True

def test_is_positive_integer_with_positive_integer_string():
    assert is_positive_integer("5") == True

def test_is_positive_integer_with_zero_string():
    assert is_positive_integer("0") == True

def test_is_positive_integer_with_negative_integer_string():
    assert is_positive_integer("-5") == True

def test_is_positive_integer_with_non_integer_string():
    assert is_positive_integer("abc") == False

def test_is_positive_integer_with_float_string():
    assert is_positive_integer("5.5") == False

def test_is_positive_integer_with_empty_string():
    assert is_positive_integer("") == False

def test_is_positive_integer_with_none():
    assert is_positive_integer(None) == False

# Test convert country name

def test_convert_country_name_valid():
    assert convert_country_name("United States") == "US"
    assert convert_country_name("Germany") == "DE"
    assert convert_country_name("Japan") == "JP"

def test_convert_country_name_special_cases():
    assert convert_country_name("Turkey") == "TR"
    assert convert_country_name("Russia") == "RU"

def test_convert_country_name_invalid():
    assert convert_country_name("Atlantis") == "XX"
    assert convert_country_name("Wakanda") == "XX"

def test_convert_country_name_case_insensitive():
    assert convert_country_name("united states") == "US"
    assert convert_country_name("germany") == "DE"
    assert convert_country_name("japan") == "JP"

def test_convert_country_name_with_spaces():
    assert convert_country_name(" United States ") == "US"
    assert convert_country_name(" Germany ") == "DE"
    assert convert_country_name(" Japan ") == "JP"


# Test generate short code and passkey

def test_generate_short_code():
    short_code = generate_short_code()
    assert len(short_code) == 6
    assert short_code.isalnum()

def test_generate_short_code_characters():
    code = generate_short_code()
    valid_characters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    assert all(c in valid_characters for c in code)

def test_generate_passkey_length():
    passkey = generate_passkey()
    assert len(passkey) == 22

def test_generate_passkey_characters():
    passkey = generate_passkey()
    valid_characters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    assert all(c in valid_characters for c in passkey)

def test_generate_short_code_uniqueness():
    codes = {generate_short_code() for _ in range(1000)}
    assert len(codes) == 1000  # Ensure all generated codes are unique

def test_generate_passkey_uniqueness():
    passkeys = {generate_passkey() for _ in range(1000)}
    assert len(passkeys) == 1000  # Ensure all generated passkeys are unique

def test_validate_string_valid():
    assert validate_string("validString123") == True
    assert validate_string("valid_string-123") == True
    assert validate_string("valid-String_123") == True

def test_validate_string_invalid():
    assert validate_string("invalid string!") == False
    assert validate_string("invalid@string") == False
    assert validate_string("invalid#string") == False
    assert validate_string("invalid$string") == False

def test_validate_string_empty():
    assert validate_string("") == True  # Assuming empty string is valid

def test_validate_string_special_characters():
    assert validate_string("valid_string-123") == True
    assert validate_string("invalid*string") == False
    assert validate_string("invalid&string") == False

def test_validate_string_numeric():
    assert validate_string("1234567890") == True

# Test missing dates in counter

def test_add_missing_dates_no_missing_dates(mocker):
    url_data = {
        "creation-date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "clicks": {
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 1,
            (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 2,
            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 3,
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 4,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 5,
            datetime.now().strftime("%Y-%m-%d"): 6,
        }
    }
    result = add_missing_dates("clicks", url_data)
    assert result == url_data

def test_add_missing_dates_with_missing_dates(mocker):
    url_data = {
        "creation-date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "clicks": {
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 1,
            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 3,
            datetime.now().strftime("%Y-%m-%d"): 6,
        }
    }
    expected_result = {
        "creation-date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "clicks": {
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 1,
            (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 0,
            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 3,
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 0,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 0,
            datetime.now().strftime("%Y-%m-%d"): 6,
        }
    }
    result = add_missing_dates("clicks", url_data)
    assert result == expected_result

def test_add_missing_dates_empty_counter(mocker):
    url_data = {
        "creation-date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "clicks": {}
    }
    expected_result = {
        "creation-date": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        "clicks": {
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 0,
            (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 0,
            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 0,
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 0,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 0,
            datetime.now().strftime("%Y-%m-%d"): 0,
        }
    }
    result = add_missing_dates("clicks", url_data)
    assert result == expected_result

# Test top four

def test_top_four_less_than_six_countries():
    country_data = {
        "USA": 100,
        "Germany": 80,
        "Japan": 60,
        "Canada": 40,
        "Australia": 20
    }
    result = top_four(country_data)
    assert result == country_data

def test_top_four_exactly_six_countries():
    country_data = {
        "USA": 100,
        "Germany": 80,
        "Japan": 60,
        "Canada": 40,
        "Australia": 20,
        "France": 10
    }
    result = top_four(country_data)
    expected_result = {
        "USA": 100,
        "Germany": 80,
        "Japan": 60,
        "Canada": 40,
        "others": 30  # Sum of "Australia" and "France"
    }
    assert result == expected_result

def test_top_four_more_than_six_countries():
    country_data = {
        "USA": 100,
        "Germany": 80,
        "Japan": 60,
        "Canada": 40,
        "Australia": 20,
        "France": 10,
        "Brazil": 5
    }
    result = top_four(country_data)
    expected_result = {
        "USA": 100,
        "Germany": 80,
        "Japan": 60,
        "Canada": 40,
        "others": 35  # Sum of "Australia", "France", and "Brazil"
    }
    assert result == expected_result

def test_top_four_with_ties():
    country_data = {
        "USA": 100,
        "Germany": 80,
        "Japan": 80,
        "Canada": 60,
        "Australia": 60,
        "France": 40,
        "Brazil": 20
    }
    result = top_four(country_data)
    expected_result = {
        "USA": 100,
        "Germany": 80,
        "Japan": 80,
        "Canada": 60,
        "others": 120  # Sum of "Australia", "France", and "Brazil"
    }
    assert result == expected_result

def test_top_four_empty_country_data():
    country_data = {}
    result = top_four(country_data)
    assert result == {}

# Test calculate click averages

def test_calculate_click_averages_same_day():
    data = {
        "counter": {
            (datetime.now() - timedelta(days=0)).strftime("%Y-%m-%d"): 10,
        },
        "total-clicks": 10,
        "creation-date": datetime.now().strftime("%Y-%m-%d")
    }
    avg_daily_clicks, avg_weekly_clicks, avg_monthly_clicks = calculate_click_averages(data)
    assert avg_daily_clicks == 10.0
    assert avg_weekly_clicks == 1.43  # 10 / 7
    assert avg_monthly_clicks == 0.33  # 10 / 30

def test_calculate_click_averages_multiple_days():
    data = {
        "counter": {
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 10,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 20,
            datetime.now().strftime("%Y-%m-%d"): 30,
        },
        "total-clicks": 60,
        "creation-date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    }
    avg_daily_clicks, avg_weekly_clicks, avg_monthly_clicks = calculate_click_averages(data)
    assert avg_daily_clicks == 20.0  # 60 / 3
    assert avg_weekly_clicks == 8.57  # 60 / 7
    assert avg_monthly_clicks == 2.0  # 60 / 30

def test_calculate_click_averages_one_week():
    data = {
        "counter": {
            (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"): 5,
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 10,
            (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 15,
            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 20,
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 25,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 30,
            datetime.now().strftime("%Y-%m-%d"): 35,
        },
        "total-clicks": 140,
        "creation-date": (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
    }
    avg_daily_clicks, avg_weekly_clicks, avg_monthly_clicks = calculate_click_averages(data)
    assert avg_daily_clicks == 20.0  # 140 / 7
    assert avg_weekly_clicks == 20.0  # 140 / 7
    assert avg_monthly_clicks == 4.67  # 140 / 30

def test_calculate_click_averages_one_month():
    data = {
        "counter": {
            (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d"): 1,
            (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d"): 2,
            (datetime.now() - timedelta(days=27)).strftime("%Y-%m-%d"): 3,
            (datetime.now() - timedelta(days=26)).strftime("%Y-%m-%d"): 4,
            (datetime.now() - timedelta(days=25)).strftime("%Y-%m-%d"): 5,
            (datetime.now() - timedelta(days=24)).strftime("%Y-%m-%d"): 6,
            (datetime.now() - timedelta(days=23)).strftime("%Y-%m-%d"): 7,
            (datetime.now() - timedelta(days=22)).strftime("%Y-%m-%d"): 8,
            (datetime.now() - timedelta(days=21)).strftime("%Y-%m-%d"): 9,
            (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"): 10,
            (datetime.now() - timedelta(days=19)).strftime("%Y-%m-%d"): 11,
            (datetime.now() - timedelta(days=18)).strftime("%Y-%m-%d"): 12,
            (datetime.now() - timedelta(days=17)).strftime("%Y-%m-%d"): 13,
            (datetime.now() - timedelta(days=16)).strftime("%Y-%m-%d"): 14,
            (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"): 15,
            (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d"): 16,
            (datetime.now() - timedelta(days=13)).strftime("%Y-%m-%d"): 17,
            (datetime.now() - timedelta(days=12)).strftime("%Y-%m-%d"): 18,
            (datetime.now() - timedelta(days=11)).strftime("%Y-%m-%d"): 19,
            (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"): 20,
            (datetime.now() - timedelta(days=9)).strftime("%Y-%m-%d"): 21,
            (datetime.now() - timedelta(days=8)).strftime("%Y-%m-%d"): 22,
            (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"): 23,
            (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d"): 24,
            (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"): 25,
            (datetime.now() - timedelta(days=4)).strftime("%Y-%m-%d"): 26,
            (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"): 27,
            (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"): 28,
            (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"): 29,
            datetime.now().strftime("%Y-%m-%d"): 30,
        },
        "total-clicks": 465,
        "creation-date": (datetime.now() - timedelta(days=29)).strftime("%Y-%m-%d")
    }
    avg_daily_clicks, avg_weekly_clicks, avg_monthly_clicks = calculate_click_averages(data)
    assert avg_daily_clicks == 15.5  # 465 / 30
    assert avg_weekly_clicks == 66.43  # 465 / 7
    assert avg_monthly_clicks == 15.5  # 465 / 30

def test_calculate_click_averages_empty_counter():
    data = {
        "counter": {},
        "total-clicks": 0,
        "creation-date": datetime.now().strftime("%Y-%m-%d")
    }
    avg_daily_clicks, avg_weekly_clicks, avg_monthly_clicks = calculate_click_averages(data)
    assert avg_daily_clicks == 0.0
    assert avg_weekly_clicks == 0.0
    assert avg_monthly_clicks == 0.0

# Test validate emoji alias

def test_validate_emoji_alias_valid_single_emoji():
    assert validate_emoji_alias("😊") == True

def test_validate_emoji_alias_valid_multiple_emojis():
    assert validate_emoji_alias("😊👍🎉") == True

def test_validate_emoji_alias_invalid_mixed_characters():
    assert validate_emoji_alias("😊abc") == False

def test_validate_emoji_alias_invalid_too_many_emojis():
    assert validate_emoji_alias("😊" * 16) == False

def test_validate_emoji_alias_empty_string():
    assert validate_emoji_alias("") == True  # Assuming empty string is valid

def test_validate_emoji_alias_url_encoded():
    assert validate_emoji_alias(unquote("%F0%9F%98%8A")) == True  # URL encoded 😊
