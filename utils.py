import re
import string
import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import sys
from emojies import EMOJIES
from urllib.parse import unquote
import emoji

load_dotenv(override=True)

MONGO_URI = os.environ["MONGODB_URI"]

client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("\n Pinged your deployment. You successfully connected to MongoDB! \n")
except Exception as e:
    print(e)

db = client["url-shortener"]
collection = db["urls"]
blocked_urls_collection = db["blocked-urls"]
# emoji_collection = db["emojis"]

def load_url_by_id(id):
    try:
        url_data = collection.find_one({"_id": id})
    except:
        url_data = None
    return url_data


def add_url_by_id(id, url_data):
    try:
        collection.insert_one({"_id": id, **url_data})
    except:
        pass


def update_url_by_id(id, url_data):
    try:
        collection.update_one({"_id": id}, {"$set": url_data})
    except:
        pass


def check_if_slug_exists(slug):
    try:
        url_data = collection.find_one({"_id": slug})
    except:
        url_data = None
    return url_data is not None


def validate_password(password):
    # Check if the password is at least 8 characters long
    if len(password) < 8:
        return False

    # Check if the password contains a letter, a number, and the allowed special characters
    if not re.search(r"[a-zA-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[@.]", password):
        return False

    # Check if there are consecutive special characters
    if re.search(r"[@.]{2}", password):
        return False

    return True


def validate_url(url):
    pattern = re.compile(
        r"^(https?:\/\/)?(www\.)?[a-zA-Z0-9]+([\-\.]{1}[a-zA-Z0-9]+)*\.[a-zA-Z]{2,6}(\:[0-9]{1,5})?(\/.*)?$"
    )

    if "spoo.me" in url:
        return False

    if re.fullmatch(pattern, url):
        return True
    else:
        return False


def validate_blocked_url(url):
    blocked_urls = blocked_urls_collection.find()
    blocked_urls = [doc["_id"] for doc in blocked_urls]

    for blocked_url in blocked_urls:
        if re.search(blocked_url, url):
            return False

    return True


def is_positive_integer(value):
    try:
        int(value)
        return True
    except ValueError:
        return False


def generate_short_code():
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for i in range(6))


def validate_string(string):
    pattern = r"^[a-zA-Z0-9_-]*$"
    return bool(re.search(pattern, string))


def add_missing_dates(key, url_data):
    counter = url_data[key]

    # Get the current date

    # Get the first and last click dates
    first_click_date = url_data["creation-date"]  # next(iter(counter.keys()))
    last_click_date = datetime.now().strftime("%Y-%m-%d")

    # Convert the click dates to datetime objects
    first_date = datetime.strptime(first_click_date, "%Y-%m-%d")
    last_date = datetime.strptime(last_click_date, "%Y-%m-%d")

    # Generate a list of dates between the first and last click dates
    date_range = [
        first_date + timedelta(days=x) for x in range((last_date - first_date).days + 1)
    ]
    all_dates = [date.strftime("%Y-%m-%d") for date in date_range]

    # Add missing dates with a counter value of 0
    for date in all_dates:
        if date not in counter:
            counter[date] = 0

    # Sort the counter dictionary by dates
    sorted_counter = {date: counter[date] for date in sorted(counter.keys())}

    # Update the url_data with the modified counter
    url_data[key] = sorted_counter

    return url_data


def top_four(dictionary):
    if len(dictionary) < 6:
        return dictionary
    sorted_dict = dict(sorted(dictionary.items(), key=lambda x: x[1], reverse=True))
    new_dict = {}
    others = 0
    for i, (key, value) in enumerate(sorted_dict.items()):
        if i < 4:
            new_dict[key] = value
        else:
            others += value

    new_dict["others"] = others
    return new_dict


def calculate_click_averages(data):
    counter = data["counter"]
    total_clicks = data["total-clicks"]
    creation_date = datetime.fromisoformat(data["creation-date"]).date()
    current_date = datetime.now().date()
    link_age = (
        1
        if (current_date - creation_date).days == 0
        else (current_date - creation_date).days
    )

    # Calculate average weekly clicks
    weekly_clicks = sum(counter.values())
    avg_weekly_clicks = round(weekly_clicks / 7, 2)

    # Calculate average daily clicks
    avg_daily_clicks = round(total_clicks / link_age, 2)

    # Calculate average monthly clicks
    avg_monthly_clicks = round(total_clicks / 30, 2)  # Assuming 30 days in a month

    return avg_daily_clicks, avg_weekly_clicks, avg_monthly_clicks


def generate_emoji_alias():
    return ''.join(random.choice(EMOJIES) for _ in range(3))


# def check_if_emoji_alias_exists(emoji_alias):
#     try:
#         emoji_data = collection.find_one({"_id": emoji_alias})
#     except:
#         emoji_data = None
#     return emoji_data is not None

def validate_emoji_alias(alias):
    alias = unquote(alias)
    emoji_list = emoji.emoji_list(alias)
    extracted_emojis = ''.join([data['emoji'] for data in emoji_list])
    if len(extracted_emojis) != len(alias) or len(emoji_list) > 15:
        return False
    else:
        return True

# def load_emoji_by_alias(alias):
#     try:
#         emoji_data = collection.find_one({"_id": alias})
#     except:
#         emoji_data = None
#     return emoji_data

# def add_emoji_by_alias(alias, emoji_data):
#     try:
#         collection.insert_one({"_id": alias, **emoji_data})
#     except:
#         pass

# def update_emoji_by_alias(alias, emoji_data):
#     try:
#         collection.update_one({"_id": alias}, {"$set": emoji_data})
#     except:
#         pass
