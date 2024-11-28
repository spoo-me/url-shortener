from datetime import datetime, timedelta
import functools
import pycountry


def convert_country_data(data):
    return [{"id": convert_country_name(k), "value": v} for k, v in data.items()]


@functools.lru_cache(maxsize=None)
def convert_country_name(country_name: str) -> str:
    try:
        return pycountry.countries.lookup(country_name.strip()).alpha_2
    except LookupError:
        if country_name == "Turkey":
            return "TR"
        elif country_name == "Russia":
            return "RU"
        return "XX"


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
    total_clicks = data["total-clicks"]
    creation_date = datetime.fromisoformat(data["creation-date"]).date()
    current_date = datetime.now().date()
    link_age = (current_date - creation_date).days + 1

    # Calculate average weekly clicks
    avg_weekly_clicks = round(total_clicks / 7, 2)

    # Calculate average daily clicks
    avg_daily_clicks = round(total_clicks / link_age, 2)

    # Calculate average monthly clicks
    avg_monthly_clicks = round(total_clicks / 30, 2)  # Assuming 30 days in a month

    return avg_daily_clicks, avg_weekly_clicks, avg_monthly_clicks
