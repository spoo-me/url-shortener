import re
import string
import random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import sys
from emojies import EMOJIES
from urllib.parse import unquote
import emoji
import pandas as pd
from flask import send_file
import io
import zipfile
from dicttoxml import dicttoxml
import json
import requests
import validators

load_dotenv(override=True)

MONGO_URI = os.environ["MONGODB_URI"]
CONTACT_WEBHOOK = os.environ["CONTACT_WEBHOOK"]
URL_REPORT_WEBHOOK = os.environ["URL_REPORT_WEBHOOK"]

client = MongoClient(MONGO_URI)

try:
    client.admin.command("ping")
    print("\n Pinged your deployment. You successfully connected to MongoDB! \n")
except Exception as e:
    print(e)

db = client["url-shortener"]
collection = db["urls"]
blocked_urls_collection = db["blocked-urls"]
emoji_collection = db["emojis"]
ip_bypasses = db["ip-exceptions"]


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


# def validate_url(url):   (OLD DEPRECATED FUNCTION)
#     pattern = re.compile(
#         r"^(https?:\/\/)?(www\.)?[a-zA-Z0-9]+([\-\.]{1}[a-zA-Z0-9]+)*\.[a-zA-Z]{2,6}(\:[0-9]{1,5})?(\/.*)?$"
#     )

#     if "spoo.me" in url:
#         return False

#     if re.fullmatch(pattern, url):
#         return True
#     else:
#         return False


def validate_url(url):
    return (
        validators.url(url, skip_ipv4_addr=True, skip_ipv6_addr=True)
        and not "spoo.me" in url
    )


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


# custom expiration time is currently really buggy and not ready for production


def validate_expiration_time(expiration_time):
    try:
        expiration_time = datetime.fromisoformat(expiration_time)
        # Check if it's timezone aware
        if expiration_time.tzinfo is None:
            print("timezone not aware")
            return False
        else:
            print("timezone aware")
            print("Expiration Time in GMT: ", expiration_time.astimezone(timezone.utc))
            print(expiration_time.tzinfo)
            # Convert to GMT if it's timezone aware
            expiration_time = expiration_time.astimezone(timezone.utc)
        if expiration_time < datetime.now(timezone.utc) + timedelta(minutes=3):
            print(expiration_time, datetime.now(timezone.utc) + timedelta(minutes=3))
            print("EXPIRATION TIME IN GMT: ", expiration_time)
            print("CURRENT TIME IN GMT: ", datetime.now(timezone.utc))
            print(
                "CURRENT TIME IN GMT + 5: ",
                datetime.now(timezone.utc) + timedelta(minutes=4.5),
            )
            print("less than 5 minutes")
            return False
        return True
    except Exception as e:
        print(e)
        return False


def convert_to_gmt(expiration_time):
    expiration_time = datetime.fromisoformat(expiration_time)
    # Check if it's timezone aware
    if expiration_time.tzinfo is None:
        return None
    else:
        # Convert to GMT if it's timezone aware
        expiration_time = expiration_time.astimezone(timezone.utc)
    return expiration_time


def generate_short_code():
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for i in range(6))


def generate_passkey():
    letters = string.ascii_lowercase + string.ascii_uppercase + string.digits
    return "".join(random.choice(letters) for i in range(22))


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
    return "".join(random.choice(EMOJIES) for _ in range(3))


def check_if_emoji_alias_exists(emoji_alias):
    try:
        emoji_data = emoji_collection.find_one({"_id": emoji_alias})
    except:
        emoji_data = None
    return emoji_data is not None


def validate_emoji_alias(alias):
    alias = unquote(alias)
    emoji_list = emoji.emoji_list(alias)
    extracted_emojis = "".join([data["emoji"] for data in emoji_list])
    if len(extracted_emojis) != len(alias) or len(emoji_list) > 15:
        return False
    else:
        return True


def load_emoji_by_alias(alias):
    try:
        emoji_data = emoji_collection.find_one({"_id": alias})
    except:
        emoji_data = None
    return emoji_data


def add_emoji_by_alias(alias, emoji_data):
    try:
        emoji_collection.insert_one({"_id": alias, **emoji_data})
    except:
        pass


def update_emoji_by_alias(alias, emoji_data):
    try:
        emoji_collection.update_one({"_id": alias}, {"$set": emoji_data})
    except:
        pass


def send_report(webhook_uri, short_code, reason, ip_address, host_uri):

    data = {
        "embeds": [
            {
                "title": f"URL Report for `{short_code}`",
                "color": 14177041,
                "url": f"{host_uri}stats/{short_code}",
                "fields": [
                    {"name": "Short Code", "value": f"```{short_code}```"},
                    {"name": "Reason", "value": f"```{reason}```"},
                    {"name": "IP Address", "value": f"```{ip_address}```"},
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {
                    "text": "spoo-me",
                    "icon_url": "https://spoo.me/static/images/favicon.png",
                },
            }
        ]
    }

    requests.post(webhook_uri, json=data)


def send_contact_message(webhook_uri, email, message):

    data = {
        "embeds": [
            {
                "title": "New Contact Message ✉️",
                "color": 9103397,
                "fields": [
                    {"name": "Email", "value": f"```{email}```"},
                    {"name": "Message", "value": f"```{message}```"},
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {
                    "text": "spoo-me",
                    "icon_url": "https://spoo.me/static/images/favicon.png",
                },
            }
        ]
    }

    requests.post(webhook_uri, json=data)


def export_to_excel(data):
    output = io.BytesIO()

    df_browser = pd.DataFrame(data["browser"].items(), columns=["Browser", "Count"])
    df_counter = pd.DataFrame(data["counter"].items(), columns=["Date", "Count"])
    df_country = pd.DataFrame(data["country"].items(), columns=["Country", "Count"])
    df_os_name = pd.DataFrame(data["os_name"].items(), columns=["OS_Name", "Count"])
    df_referrer = pd.DataFrame(data["referrer"].items(), columns=["Referrer", "Count"])
    df_unique_browser = pd.DataFrame(
        data["unique_browser"].items(), columns=["Browser", "Count"]
    )
    df_unique_counter = pd.DataFrame(
        data["unique_counter"].items(), columns=["Date", "Count"]
    )
    df_unique_country = pd.DataFrame(
        data["unique_country"].items(), columns=["Country", "Count"]
    )
    df_unique_os_name = pd.DataFrame(
        data["unique_os_name"].items(), columns=["OS_Name", "Count"]
    )
    df_unique_referrer = pd.DataFrame(
        data["unique_referrer"].items(), columns=["Referrer", "Count"]
    )

    df_general_info = pd.DataFrame(
        {
            "TOTAL CLICKS": [data["total-clicks"]],
            "TOTAL UNIQUE CLICKS": [data["total_unique_clicks"]],
            "URL": [data["url"]],
            "SHORT CODE": [data["_id"]],
            "MAX CLICKS": [data["max-clicks"]],
            "EXPIRATION TIME": [data["expiration-time"]],
            "PASSWORD": [data["password"]],
            "CREATION DATE": [data["creation-date"]],
            "EXPIRED": [data["expired"]],
            "AVERAGE DAILY CLICKS": [data["average_daily_clicks"]],
            "AVERAGE MONTHLY CLICKS": [data["average_monthly_clicks"]],
            "AVERAGE WEEKLY CLICKS": [data["average_weekly_clicks"]],
            "LAST CLICK": [data["last-click"]],
            "LAST CLICK BROSWER": [data["last-click-browser"]],
            "LAST CLICK OS": [data["last-click-os"]],
        }
    )

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_general_info.to_excel(writer, sheet_name="General_Info", index=False)

        df_browser.to_excel(writer, sheet_name="Browser", index=False)
        df_counter.to_excel(writer, sheet_name="Counter", index=False)
        df_country.to_excel(writer, sheet_name="Country", index=False)
        df_os_name.to_excel(writer, sheet_name="OS_Name", index=False)
        df_referrer.to_excel(writer, sheet_name="Referrer", index=False)
        df_unique_browser.to_excel(writer, sheet_name="Unique_Browser", index=False)
        df_unique_counter.to_excel(writer, sheet_name="Unique_Counter", index=False)
        df_unique_country.to_excel(writer, sheet_name="Unique_Country", index=False)
        df_unique_os_name.to_excel(writer, sheet_name="Unique_OS_Name", index=False)
        df_unique_referrer.to_excel(writer, sheet_name="Unique_Referrer", index=False)

    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="spoo-me-export.xlsx",
    )


def export_to_csv(data):
    output = io.BytesIO()

    df_browser = pd.DataFrame(data["browser"].items(), columns=["Browser", "Count"])
    df_counter = pd.DataFrame(data["counter"].items(), columns=["Date", "Count"])
    df_country = pd.DataFrame(data["country"].items(), columns=["Country", "Count"])
    df_os_name = pd.DataFrame(data["os_name"].items(), columns=["OS_Name", "Count"])
    df_referrer = pd.DataFrame(data["referrer"].items(), columns=["Referrer", "Count"])
    df_unique_browser = pd.DataFrame(
        data["unique_browser"].items(), columns=["Browser", "Count"]
    )
    df_unique_counter = pd.DataFrame(
        data["unique_counter"].items(), columns=["Date", "Count"]
    )
    df_unique_country = pd.DataFrame(
        data["unique_country"].items(), columns=["Country", "Count"]
    )
    df_unique_os_name = pd.DataFrame(
        data["unique_os_name"].items(), columns=["OS_Name", "Count"]
    )
    df_unique_referrer = pd.DataFrame(
        data["unique_referrer"].items(), columns=["Referrer", "Count"]
    )

    df_general_info = pd.DataFrame(
        {
            "TOTAL CLICKS": [data["total-clicks"]],
            "TOTAL UNIQUE CLICKS": [data["total_unique_clicks"]],
            "": [data["url"]],
            "SHORT CODE": [data["_id"]],
            "MAX CLICKS": [data["max-clicks"]],
            "EXPIRATION TIME": [data["expiration-time"]],
            "PASSWORD": [data["password"]],
            "CREATION DATE": [data["creation-date"]],
            "EXPIRED": [data["expired"]],
            "AVERAGE DAILY CLICKS": [data["average_daily_clicks"]],
            "AVERAGE MONTHLY CLICKS": [data["average_monthly_clicks"]],
            "AVERAGE WEEKLY CLICKS": [data["average_weekly_clicks"]],
            "LAST CLICK": [data["last-click"]],
            "LAST CLICK BROSWER": [data["last-click-browser"]],
            "LAST CLICK OS": [data["last-click-os"]],
        }
    )

    with zipfile.ZipFile(output, mode="w") as zipf:
        df_general_info.to_csv(zipf.open("general_info.csv", "w"), index=False)
        df_browser.to_csv(zipf.open("browser.csv", "w"), index=False)
        df_counter.to_csv(zipf.open("counter.csv", "w"), index=False)
        df_country.to_csv(zipf.open("country.csv", "w"), index=False)
        df_os_name.to_csv(zipf.open("os_name.csv", "w"), index=False)
        df_referrer.to_csv(zipf.open("referrer.csv", "w"), index=False)
        df_unique_browser.to_csv(zipf.open("unique_browser.csv", "w"), index=False)
        df_unique_counter.to_csv(zipf.open("unique_counter.csv", "w"), index=False)
        df_unique_country.to_csv(zipf.open("unique_country.csv", "w"), index=False)
        df_unique_os_name.to_csv(zipf.open("unique_os_name.csv", "w"), index=False)
        df_unique_referrer.to_csv(zipf.open("unique_referrer.csv", "w"), index=False)

    output.seek(0)

    return send_file(
        output,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"spoo-me-export-csv.zip",
    )


def export_to_json(data):
    output = io.StringIO()

    json.dump(data, output, indent=4)
    output.seek(0)

    output_bytes = io.BytesIO(output.getvalue().encode())

    return send_file(
        output_bytes,
        mimetype="application/json",
        as_attachment=True,
        download_name="spoo-me-export.json",
    )


def export_to_xml(data):
    # Convert dictionary to XML
    xml = dicttoxml(data)

    # Create BytesIO object and write XML data to it
    output = io.BytesIO()
    output.write(xml)
    output.seek(0)

    # Send file
    return send_file(
        output, mimetype="application/xml", as_attachment=True, download_name="data.xml"
    )
