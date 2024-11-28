import pytest
import requests_mock
from utils.contact_utils import verify_hcaptcha


def test_verify_hcaptcha_success():
    with requests_mock.Mocker() as m:
        m.post(
            "https://hcaptcha.com/siteverify", json={"success": True}, status_code=200
        )
        assert verify_hcaptcha("valid_token")


def test_verify_hcaptcha_failure():
    with requests_mock.Mocker() as m:
        m.post(
            "https://hcaptcha.com/siteverify", json={"success": False}, status_code=200
        )
        assert not verify_hcaptcha("invalid_token")


def test_verify_hcaptcha_http_error():
    with requests_mock.Mocker() as m:
        m.post("https://hcaptcha.com/siteverify", status_code=500)
        assert not verify_hcaptcha("any_token")


if __name__ == "__main__":
    pytest.main()
