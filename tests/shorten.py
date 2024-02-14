import sys
import requests
import random
import string
import datetime

url = "http://localhost:8000/"

alias = ''.join(random.choice(string.ascii_lowercase) for i in range(6))

payload = {
    "url": "https://example.com",
    "alias": alias,
    "max-clicks": 10,
    "expiration": (datetime.datetime.now() + datetime.timedelta(days=5)).timestamp(),
    "password": "SuperStrongPassword@18322"
}

headers = {
    "Accept": "application/json"
}

response = requests.post(url, data=payload, headers=headers)

if response.status_code == 200:
    shortened_url = response.json()
    print(f"Shortened URL: {shortened_url['short_url']}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)
    sys.exit(1)
