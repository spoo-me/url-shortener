import sys
import requests
import random
import string

if len(sys.argv) != 2:
    print("Usage: python test_api.py <ngrok_url>")
    sys.exit(1)

ngrok_url = sys.argv[1]

url = f"{ngrok_url}"

alias = ''.join(random.choice(string.ascii_lowercase) for i in range(6))

payload = {
    "url": "https://example.com",
    "alias": alias,
    "max-clicks": 10,
    "password": "SuperStrongPassword@18322"
}

headers = {
    "Accept": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

if response.status_code == 200:
    shortened_url = response.json()
    print(f"Shortened URL: {shortened_url['short_url']}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
    sys.exit(1)
