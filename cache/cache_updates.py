import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from walrus import Database
from .redis_client import get_redis
from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class ClickData:
    country: str
    browser: str
    os: str
    referrer: str
    ip: str
    redirect_time: str
    bot: str


class ClickBuffer:
    def __init__(self, ttl_seconds: int = 60 * 60) -> None:
        self.r: Optional[Database] = get_redis()
        self.ttl_seconds: int = ttl_seconds
        if self.r is None:
            log.warning("click_buffer_unavailable")

    def add_data(self, slug: str, click: ClickData) -> None:
        if not self.r:
            return
        now: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
        pipe = self.r.pipeline()

        pipe.sadd("slugs", slug)

        # Incremental Counts
        pipe.hincrby(f"counts:{slug}", "total-clicks", 1)
        pipe.hincrby(f"counts:{slug}", f"country.{click.country}", 1)
        pipe.hincrby(f"counts:{slug}", f"browser.{click.browser}", 1)
        pipe.hincrby(f"counts:{slug}", f"os_name.{click.os}", 1)
        pipe.hincrby(f"counts:{slug}", f"counter.{now.strftime('%Y-%m-%d')}", 1)

        if click.referrer:
            pipe.hincrby(f"counts:{slug}", f"referrer.{click.referrer}", 1)
        if click.bot:
            pipe.hincrby(f"counts:{slug}", f"bots.{click.bot}", 1)

        # Meta
        pipe.hset(f"meta:{slug}", "last-click", now.strftime("%Y-%m-%d %H:%M:%S"))
        pipe.hset(f"meta:{slug}", "last-click-browser", click.browser)
        pipe.hset(f"meta:{slug}", "last-click-os", click.os)
        pipe.hset(f"meta:{slug}", "last-click-country", click.country)

        # IP sets
        pipe.sadd(f"ips:{slug}:all", click.ip)
        pipe.sadd(f"ips:{slug}:browser.{click.browser}", click.ip)
        pipe.sadd(f"ips:{slug}:os.{click.os}", click.ip)
        pipe.sadd(f"ips:{slug}:country.{click.country}", click.ip)

        if click.referrer:
            pipe.sadd(f"ips:{slug}:referrer.{click.referrer}", click.ip)

        # Expiry
        pipe.expire(f"counts:{slug}", self.ttl_seconds)
        pipe.expire(f"meta:{slug}", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:all", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:browser.{click.browser}", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:os.{click.os}", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:country.{click.country}", self.ttl_seconds)
        if click.referrer:
            pipe.expire(f"ips:{slug}:referrer.{click.referrer}", self.ttl_seconds)

        pipe.execute()

    def pull(self, slug: str) -> Optional[Dict[str, Any]]:
        if not self.r:
            return None
        if not self.check_exists(slug):
            return None

        cnt_keys: str = f"counts:{slug}"
        meta_keys: str = f"meta:{slug}"

        counts = self.r.hgetall(cnt_keys)
        meta = self.r.hgetall(meta_keys)

        ip_pattern: str = f"ips:{slug}:*"
        ip_keys = list(self.r.scan_iter(ip_pattern))

        pipe = self.r.pipeline()
        for k in ip_keys:
            pipe.smembers(k)
        ip_sets = pipe.execute()

        inc: Dict[str, Any] = {}
        for k, v in counts.items():
            key: List[str] = k.decode().split(".")
            if len(key) < 2:
                inc[key[0]] = int(v)
                continue
            if key[0] not in inc:
                inc[key[0]] = {}
            inc[key[0]][key[1]] = int(v)

        set_: Dict[str, Any] = {k.decode(): v.decode() for k, v in meta.items()}

        by_dim: Dict[str, Any] = {}
        for k, v in zip(ip_keys, ip_sets):
            key: List[str] = k.decode().split(f"ips:{slug}:")[1].split(".")
            if len(key) < 2:
                by_dim[key[0]] = [ip.decode() for ip in v]
                continue
            if key[0] not in by_dim:
                by_dim[key[0]] = {}
            by_dim[key[0]][key[1]] = [ip.decode() for ip in v]

        self.r.delete(cnt_keys, meta_keys, *ip_keys)
        self.r.srem("slugs", slug)

        return {"slug": slug, "inc": inc, "set": set_, "addtoset": by_dim}

    def pull_all(self) -> List[Dict[str, Any]]:
        if not self.r:
            return []
        results: List[dict] = []
        slugs = self.r.smembers("slugs")

        for raw in slugs:
            slug: str = raw.decode()
            parsed = self.pull(slug)
            if parsed:
                results.append(parsed)
            else:
                self.r.srem("slugs", slug)

        return results

    def check_exists(self, slug: str) -> bool:
        if not self.r:
            return False
        return self.r.sismember("slugs", slug)
