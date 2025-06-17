import re
import tldextract
from utils.url_utils import get_country
from workers.async_mongo import get_async_db
from loguru import logger

# Initialize extractor without disk caching
tld_extractor = tldextract.TLDExtract(cache_dir=None)


async def handle_click_event(data: dict):
    """
    Async processing of click analytics and updating MongoDB.
    """
    # Ensure DB is initialized
    db = await get_async_db()

    short_code = data.get("short_code")
    os_name = data.get("os_name")
    browser = data.get("browser")
    referrer = data.get("referrer")
    ip = data.get("ip")
    timestamp = data.get("timestamp")
    unique_click = data.get("is_unique_click")
    bot_name = data.get("bot_name")
    is_emoji = data.get("is_emoji", False)

    # Enrich country info
    country = get_country(ip) or None
    if country:
        country = country.replace(".", " ")

    # Build update document
    updates = {"$inc": {}, "$set": {}, "$addToSet": {}}

    # Process referrer domain
    if referrer:
        raw = tld_extractor(referrer)
        domain = f"{raw.domain}.{raw.suffix}" if raw.suffix else raw.domain
        sanitized = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", domain)
        updates["$inc"][f"referrer.{sanitized}.counts"] = 1
        updates["$addToSet"][f"referrer.{sanitized}.ips"] = ip

    # Country stats
    if country:
        updates["$inc"][f"country.{country}.counts"] = 1
        updates["$addToSet"][f"country.{country}.ips"] = ip

    # Browser & OS stats
    updates["$inc"][f"browser.{browser}.counts"] = 1
    updates["$addToSet"][f"browser.{browser}.ips"] = ip
    updates["$inc"][f"os_name.{os_name}.counts"] = 1
    updates["$addToSet"][f"os_name.{os_name}.ips"] = ip

    # Bot counts
    if bot_name:
        sanitized_bot = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", bot_name)
        updates["$inc"][f"bots.{sanitized_bot}"] = 1

    # Daily and unique counters
    date_str = timestamp.split()[0]
    updates["$inc"][f"counter.{date_str}"] = 1
    if unique_click:
        updates["$inc"][f"unique_counter.{date_str}"] = 1

    # Global clicks
    updates["$addToSet"]["ips"] = ip
    updates["$inc"]["total-clicks"] = 1

    # Last click info
    updates["$set"]["last-click"] = timestamp
    updates["$set"]["last-click-browser"] = browser
    updates["$set"]["last-click-os"] = os_name
    updates["$set"]["last-click-country"] = country

    # Determine correct collection
    collection = db.emojis if is_emoji else db.urls

    # Perform atomic update
    try:
        await collection.update_one({"_id": short_code}, updates, upsert=True)
        logger.info(f"[✓] Processed analytics for {short_code}")
    except Exception as e:
        logger.error(f"[!] Error updating MongoDB: {e}")
        pass
