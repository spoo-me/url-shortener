import sys
import requests
import random
import string

BASE_URL = "http://localhost:8000"


def random_alias(length=6):
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


def create_v1_url(alias):
    """Create a V1 URL for testing"""
    response = requests.post(
        f"{BASE_URL}/",
        data={"url": "https://example.com/stats-test", "alias": alias},
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200, f"Failed to create URL: {response.text}"
    return alias


def create_v2_url():
    """Create a V2 URL for testing"""
    response = requests.post(
        f"{BASE_URL}/api/v1/shorten",
        json={"url": "https://example.com/stats-v2"},
    )
    assert response.status_code == 201, f"Failed to create URL: {response.text}"
    return response.json()["alias"]


def click_url(alias):
    """Simulate a click on the URL"""
    requests.get(f"{BASE_URL}/{alias}", allow_redirects=False)


def test_v1_stats(alias):
    """Test stats for V1 URL"""
    response = requests.post(f"{BASE_URL}/stats/{alias}")
    assert response.status_code == 200, f"V1 stats failed: {response.text}"
    data = response.json()
    assert "total-clicks" in data, "Missing total-clicks"
    assert "url" in data, "Missing url"
    print(f"✅ V1 stats: {data['total-clicks']} clicks")
    return data


def test_v2_stats(alias):
    """Test stats for V2 URL via API"""
    response = requests.get(
        f"{BASE_URL}/api/v1/stats",
        params={"scope": "anon", "short_code": alias}
    )
    assert response.status_code == 200, f"V2 stats failed: {response.status_code} - {response.text}"
    data = response.json()
    assert "summary" in data or "total_clicks" in data or "total-clicks" in data, "Missing click data"
    print(f"✅ V2 stats retrieved for {alias}")
    return data


def test_stats_nonexistent():
    """Test stats for non-existent URL"""
    response = requests.post(f"{BASE_URL}/stats/nonexistent12345")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    print("✅ Non-existent URL stats returns 404")


def test_preview(alias):
    """Test preview endpoint"""
    response = requests.get(f"{BASE_URL}/{alias}+")
    assert response.status_code == 200, f"Preview failed: {response.status_code}"
    assert "example.com" in response.text, "Preview missing destination"
    print("✅ Preview endpoint works")


def main():
    print("\n🧪 Running Stats Tests\n")
    
    try:
        # Create test URLs
        v1_alias = random_alias()
        create_v1_url(v1_alias)
        print(f"✅ Created V1 test URL: {v1_alias}")
        
        v2_alias = create_v2_url()
        print(f"✅ Created V2 test URL: {v2_alias}")
        
        # Simulate clicks
        click_url(v1_alias)
        click_url(v1_alias)
        click_url(v2_alias)
        print("✅ Simulated clicks")
        
        # Test stats
        test_v1_stats(v1_alias)
        test_v2_stats(v2_alias)
        test_stats_nonexistent()
        
        # Test preview
        test_preview(v1_alias)
        
        print("\n✅ All stats tests passed!\n")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
