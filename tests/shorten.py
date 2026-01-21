import sys
import requests
import random
import string

BASE_URL = "http://localhost:8000"


def random_alias(length=6):
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


def test_v1_create_url():
    """Test V1 legacy URL creation"""
    alias = random_alias()
    response = requests.post(
        f"{BASE_URL}/",
        data={"url": "https://example.com/v1", "alias": alias},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, f"V1 create failed: {response.text}"
    data = response.json()
    assert "short_url" in data, "Missing short_url in response"
    assert alias in data["short_url"], "Alias not in short_url"
    print(f"✅ V1 URL created: {data['short_url']}")
    return alias


def test_v1_duplicate_alias(alias):
    """Test V1 rejects duplicate alias"""
    response = requests.post(
        f"{BASE_URL}/",
        data={"url": "https://example.com/dupe", "alias": alias},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    print("✅ V1 duplicate alias rejected")


def test_v1_redirection(alias):
    """Test V1 URL redirects correctly"""
    response = requests.get(f"{BASE_URL}/{alias}", allow_redirects=False)
    assert response.status_code in (301, 302, 307, 308), (
        f"Expected redirect, got {response.status_code}"
    )
    assert response.headers.get("Location") == "https://example.com/v1"
    print("✅ V1 redirection works")


def test_v2_create_url():
    """Test V2 API URL creation"""
    response = requests.post(
        f"{BASE_URL}/api/v1/shorten",
        json={"url": "https://example.com/v2"},
    )
    assert response.status_code == 201, f"V2 create failed: {response.text}"
    data = response.json()
    assert "short_url" in data, "Missing short_url in response"
    assert "alias" in data, "Missing alias in response"
    print(f"✅ V2 URL created: {data['short_url']}")
    return data["alias"]


def test_v2_redirection(alias):
    """Test V2 URL redirects correctly"""
    response = requests.get(f"{BASE_URL}/{alias}", allow_redirects=False)
    assert response.status_code in (301, 302, 307, 308), (
        f"Expected redirect, got {response.status_code}"
    )
    assert response.headers.get("Location") == "https://example.com/v2"
    print("✅ V2 redirection works")


def test_v2_with_password():
    """Test V2 password-protected URL"""
    response = requests.post(
        f"{BASE_URL}/api/v1/shorten",
        json={"url": "https://example.com/secret", "password": "Test@123"},
    )
    assert response.status_code == 201, f"V2 password create failed: {response.text}"
    data = response.json()
    print(f"✅ V2 password-protected URL created: {data['short_url']}")

    # Should show password page (401), not redirect
    response = requests.get(data["short_url"], allow_redirects=False)
    assert response.status_code == 401, (
        f"Expected 401 password page, got {response.status_code}"
    )
    print("✅ V2 password protection works")


def test_emoji_create_url():
    """Test emoji URL creation"""
    response = requests.post(
        f"{BASE_URL}/emoji",
        data={"url": "https://example.com/emoji"},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, f"Emoji create failed: {response.text}"
    data = response.json()
    assert "short_url" in data, "Missing short_url in response"
    print(f"✅ Emoji URL created: {data['short_url']}")
    return data["short_url"]


def test_emoji_redirection(short_url):
    """Test emoji URL redirects correctly"""
    response = requests.get(short_url, allow_redirects=False)
    assert response.status_code in (301, 302, 307, 308), (
        f"Expected redirect, got {response.status_code}"
    )
    assert response.headers.get("Location") == "https://example.com/emoji"
    print("✅ Emoji redirection works")


def test_invalid_url():
    """Test invalid URL is rejected"""
    response = requests.post(
        f"{BASE_URL}/api/v1/shorten",
        json={"url": "not-a-valid-url"},
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    print("✅ Invalid URL rejected")


def test_missing_url():
    """Test missing URL is rejected"""
    response = requests.post(
        f"{BASE_URL}/api/v1/shorten",
        json={},
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    print("✅ Missing URL rejected")


def test_404_nonexistent():
    """Test 404 for non-existent short URL"""
    response = requests.get(f"{BASE_URL}/nonexistent12345", allow_redirects=False)
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    print("✅ Non-existent URL returns 404")


def test_metrics():
    """Test metrics endpoint"""
    response = requests.get(f"{BASE_URL}/metric")
    assert response.status_code == 200, f"Metrics failed: {response.text}"
    data = response.json()
    assert "total-shortlinks" in data, "Missing total-shortlinks"
    assert "total-clicks" in data, "Missing total-clicks"
    print(
        f"✅ Metrics: {data['total-shortlinks']} links, {data['total-clicks']} clicks"
    )


def main():
    print("\n🧪 Running URL Shortener Tests\n")

    try:
        # V1 Tests
        v1_alias = test_v1_create_url()
        test_v1_duplicate_alias(v1_alias)
        test_v1_redirection(v1_alias)

        # V2 Tests
        v2_alias = test_v2_create_url()
        test_v2_redirection(v2_alias)
        test_v2_with_password()

        # Emoji Tests
        emoji_url = test_emoji_create_url()
        test_emoji_redirection(emoji_url)

        # Error Cases
        test_invalid_url()
        test_missing_url()
        test_404_nonexistent()

        # Metrics
        test_metrics()

        print("\n✅ All tests passed!\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
