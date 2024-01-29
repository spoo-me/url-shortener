import requests
import json

short_code = "exa"
password = "Example@12"
base_url = "http://localhost:8000"

payload = {
    "password": password
}

# Make the request
response = requests.post(
    f"{base_url}/stats/{short_code}",
    data = payload
)

# Check the response
if response.status_code == 200:
    # If the request was successful, print the URL statistics
    url_stats = response.json()
    print(json.dumps(url_stats, indent=4))
else:
    # If the request failed, print the error message
    print(f"Error: {response.status_code}")
    print(response.text)
