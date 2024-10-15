import pytest
import requests
import requests_mock
from utils import verify_hcaptcha, hcaptcha_secret


def test_verify_hcaptcha_success():
    with requests_mock.Mocker() as m:
        m.post("https://hcaptcha.com/siteverify", json={"success": True}, status_code=200)
        assert verify_hcaptcha("valid_token") == True

def test_verify_hcaptcha_failure():
    with requests_mock.Mocker() as m:
        m.post("https://hcaptcha.com/siteverify", json={"success": False}, status_code=200)
        assert verify_hcaptcha("invalid_token") == False

def test_verify_hcaptcha_http_error():
    with requests_mock.Mocker() as m:
        m.post("https://hcaptcha.com/siteverify", status_code=500)
        assert verify_hcaptcha("any_token") == False

if __name__ == "__main__":
    pytest.main()