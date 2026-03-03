"""
Click handlers — one class per URL schema.

Each handler implements the ClickHandler protocol, receives its dependencies
via constructor injection, and reads all click metadata from the ClickContext.
"""

from __future__ import annotations

import re
import time as time_module
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from ua_parser import parse as ua_parse
import tldextract

from errors import ForbiddenError, ValidationError
from infrastructure.cache.url_cache import UrlCache
from infrastructure.geoip import GeoIPService
from repositories.click_repository import ClickRepository
from repositories.legacy.emoji_url_repository import EmojiUrlRepository
from repositories.legacy.legacy_url_repository import LegacyUrlRepository
from repositories.url_repository import UrlRepository
from schemas.models.base import ANONYMOUS_OWNER_ID
from schemas.models.click import ClickDoc, ClickMeta
from services.click.protocol import ClickContext
from shared.bot_detection import get_bot_name, is_bot_request
from shared.logging import get_logger

log = get_logger(__name__)

_tld_extractor = tldextract.TLDExtract(cache_dir=None)


class V2ClickHandler:
    """Records a click for a v2 URL in the time-series clicks collection."""

    def __init__(
        self,
        click_repo: ClickRepository,
        url_repo: UrlRepository,
        geoip: GeoIPService,
        url_cache: UrlCache,
    ) -> None:
        self._click_repo = click_repo
        self._url_repo = url_repo
        self._geoip = geoip
        self._url_cache = url_cache

    async def handle(self, context: ClickContext) -> None:
        """
        Record a click for a v2 URL in the time-series clicks collection.

        If block_bots is True and the request is from a bot, analytics are
        skipped but no exception is raised — the redirect still proceeds.

        Raises:
            ValidationError: Missing or unparseable User-Agent header.
        """
        url_data = context.url_data
        short_code = context.short_code
        client_ip = context.client_ip
        start_time = context.start_time
        user_agent = context.user_agent
        referrer = context.referrer
        cf_city = context.cf_city

        if not user_agent:
            raise ValidationError("Invalid User-Agent")

        try:
            ua = ua_parse(user_agent)
        except Exception:
            raise ValidationError(
                "An internal error occurred while processing the User-Agent"
            )

        if not ua or not ua.user_agent or not ua.os:
            raise ValidationError("Invalid User-Agent")

        os_name = ua.os.family
        browser = ua.user_agent.family

        # Referrer sanitization (v2 style)
        sanitized_referrer: Optional[str] = None
        if referrer:
            ext = _tld_extractor(referrer)
            domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
            # Remove MongoDB-unsafe chars and control characters
            domain = re.sub(r"[$\x00-\x1F\x7F-\x9F]", "_", domain)
            sanitized_referrer = re.sub(r"[^a-zA-Z0-9.-]", "_", domain)

        # GeoIP (falls back to "Unknown" when DB unavailable or lookup fails)
        country = await self._geoip.get_country(client_ip)
        city = await self._geoip.get_city(client_ip) or cf_city

        redirect_ms = int((time_module.perf_counter() - start_time) * 1000)

        # Bot detection
        is_bot = is_bot_request(user_agent)
        bot_name = get_bot_name(user_agent) if is_bot else None

        if url_data.block_bots and is_bot:
            log.info(
                "bot_blocked",
                short_code=short_code,
                bot_name=bot_name or "generic",
                schema="v2",
            )
            return  # Skip analytics; redirect still proceeds

        # Build and insert ClickDoc
        url_id = ObjectId(url_data._id)
        owner_id = (
            ObjectId(url_data.owner_id) if url_data.owner_id else ANONYMOUS_OWNER_ID
        )

        curr_time = datetime.now(timezone.utc)
        click_doc = ClickDoc(
            clicked_at=curr_time,
            meta=ClickMeta(
                url_id=url_id,
                short_code=short_code,
                owner_id=owner_id,
            ),
            ip_address=client_ip,
            country=country or "Unknown",
            city=city or "Unknown",
            browser=browser,
            os=os_name,
            redirect_ms=redirect_ms,
            referrer=sanitized_referrer,
            bot_name=bot_name,
        )

        await self._click_repo.insert(click_doc.to_mongo())
        await self._url_repo.increment_clicks(url_id, last_click_time=curr_time)

        # Max-clicks expiry — atomic conditional update
        if url_data.max_clicks:
            expired = await self._url_repo.expire_if_max_clicks(
                url_id, url_data.max_clicks
            )
            if expired:
                log.info(
                    "url_expired",
                    url_id=str(url_id),
                    short_code=short_code,
                    reason="max_clicks_reached",
                    max_clicks=url_data.max_clicks,
                )
                await self._url_cache.invalidate(short_code)


class LegacyClickHandler:
    """Records a click for a v1 or emoji URL via embedded document update."""

    def __init__(
        self,
        legacy_repo: LegacyUrlRepository,
        emoji_repo: EmojiUrlRepository,
        geoip: GeoIPService,
    ) -> None:
        self._legacy_repo = legacy_repo
        self._emoji_repo = emoji_repo
        self._geoip = geoip

    async def handle(self, context: ClickContext) -> None:
        """
        Record a click for a v1 or emoji URL via embedded document update.

        Bot handling differs from v2: blocked bots raise ForbiddenError and
        the redirect is also blocked (not just analytics).

        Raises:
            ValidationError: Missing or unparseable User-Agent.
            ForbiddenError:  Bot blocked (v1 behavior — redirect is prevented).
        """
        url_data = context.url_data
        short_code = context.short_code
        is_emoji = context.is_emoji
        client_ip = context.client_ip
        start_time = context.start_time
        user_agent = context.user_agent
        referrer = context.referrer

        if not user_agent:
            raise ValidationError("Invalid User-Agent")

        ua = ua_parse(user_agent)
        if not ua or not ua.user_agent or not ua.os:
            raise ValidationError("Invalid User-Agent")

        os_name = ua.os.family
        browser = ua.user_agent.family

        # Referrer extraction (v1 style — less sanitization than v2)
        referrer_domain: Optional[str] = None
        if referrer:
            ext = _tld_extractor(referrer)
            domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
            referrer_domain = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", domain)

        # GeoIP
        country = await self._geoip.get_country(client_ip)
        if country:
            country = country.replace(".", " ")

        # Build update document
        updates: dict = {"$inc": {}, "$set": {}, "$addToSet": {}}

        if referrer_domain:
            updates["$inc"][f"referrer.{referrer_domain}.counts"] = 1
            updates["$addToSet"][f"referrer.{referrer_domain}.ips"] = client_ip

        updates["$inc"][f"country.{country}.counts"] = 1
        updates["$addToSet"][f"country.{country}.ips"] = client_ip
        updates["$inc"][f"browser.{browser}.counts"] = 1
        updates["$addToSet"][f"browser.{browser}.ips"] = client_ip
        updates["$inc"][f"os_name.{os_name}.counts"] = 1
        updates["$addToSet"][f"os_name.{os_name}.ips"] = client_ip

        # Bot detection (v1: blocked bot raises ForbiddenError)
        is_bot = is_bot_request(user_agent)
        if is_bot:
            if url_data.block_bots:
                bot_name = get_bot_name(user_agent)
                log.info(
                    "bot_blocked",
                    short_code=short_code,
                    bot_name=bot_name or "generic",
                    schema="v1",
                )
                raise ForbiddenError("Access Denied, Bots not allowed")
            bot_name = get_bot_name(user_agent)
            if bot_name:
                sanitized_bot = re.sub(r"[.$\x00-\x1F\x7F-\x9F]", "_", str(bot_name))
                updates["$inc"][f"bots.{sanitized_bot}"] = 1

        # Daily counters
        today = str(datetime.now(timezone.utc)).split()[0]
        updates["$inc"][f"counter.{today}"] = 1

        # Unique click detection.
        # ips are not tracked in UrlCacheData — defaults to empty list,
        # meaning every click appears unique. This matches the cache-hit
        # behavior in the legacy redirector (where cached url_data also
        # lacks the ips field).
        updates["$inc"][f"unique_counter.{today}"] = 1

        updates["$addToSet"]["ips"] = client_ip
        updates["$inc"]["total-clicks"] = 1

        # Last click metadata
        current_time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        updates["$set"]["last-click"] = current_time_str
        updates["$set"]["last-click-browser"] = browser
        updates["$set"]["last-click-os"] = os_name
        updates["$set"]["last-click-country"] = country

        # Average redirection time (exponential moving average, alpha=0.1)
        # curr_avg defaults to 0 since UrlCacheData doesn't carry this field
        end_time = time_module.perf_counter()
        redirection_time = (end_time - start_time) * 1000
        curr_avg = 0.0
        alpha = 0.1
        updates["$set"]["average_redirection_time"] = round(
            (1 - alpha) * curr_avg + alpha * redirection_time, 2
        )

        # Persist
        if is_emoji:
            await self._emoji_repo.update(short_code, updates)
        else:
            await self._legacy_repo.update(short_code, updates)
