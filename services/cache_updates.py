import redis, datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from redis.client import Pipeline

@dataclass
class clickData:
    "Class to hold the data of a URL Click"
    country: str
    browser: str
    os: str
    referrer: str
    ip: str
    redirect_time: str
    bot: str

class cache_updates:
    def __init__(self, redis_uri: str, ttl_seconds: int = 60*60) -> None:
        """
        Intialize the cache_updates class
        :param redis_uri:  URI string for the Redis connection
        """
        self.r: redis.Redis = redis.Redis.from_url(redis_uri)
        self.ttl_seconds: int = ttl_seconds

    def add_data(self, slug:str, clickData: clickData) -> None:
        """
        Add the data of a particular click to the cache
        :param slug: Slug of the URL
        :param data: Data of the click
        """
        now: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
        pipe: Pipeline = self.r.pipeline()

        pipe.sadd("slugs", slug)

        # Incremental Counts
        pipe.hincrby(f"counts:{slug}", "total-clicks", 1)
        pipe.hincrby(f"counts:{slug}", f"country.{clickData.country}", 1)
        pipe.hincrby(f"counts:{slug}", f"browser.{clickData.browser}", 1)
        pipe.hincrby(f"counts:{slug}", f"os_name.{clickData.os}", 1)
        pipe.hincrby(f"counts:{slug}", f"counter.{now.strftime('%Y-%m-%d')}", 1)

        # redirection time not implemented
        # max-clicks expiry not handled

        if clickData.referrer:
            pipe.hincrby(f"counts:{slug}", f"referrer.{clickData.referrer}", 1)
        if clickData.bot:
            pipe.hincrby(f"counts:{slug}", f"bots.{clickData.bot}", 1)

        # Meta
        pipe.hset(f"meta:{slug}", "last-click", now.strftime('%Y-%m-%d %H:%M:%S'))
        pipe.hset(f"meta:{slug}", "last-click-browser", clickData.browser)
        pipe.hset(f"meta:{slug}", "last-click-os", clickData.os)
        pipe.hset(f"meta:{slug}", "last-click-country", clickData.country)

        # IP sets
        pipe.sadd(f"ips:{slug}:all", clickData.ip)
        pipe.sadd(f"ips:{slug}:browser.{clickData.browser}", clickData.ip)
        pipe.sadd(f"ips:{slug}:os.{clickData.os}", clickData.ip)
        pipe.sadd(f"ips:{slug}:country.{clickData.country}", clickData.ip)

        if clickData.referrer:
            pipe.sadd(f"ips:{slug}:referrer.{clickData.referrer}", clickData.ip)

        # Add expiry to all keys
        pipe.expire(f"counts:{slug}", self.ttl_seconds)
        pipe.expire(f"meta:{slug}", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:all", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:browser.{clickData.browser}", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:os.{clickData.os}", self.ttl_seconds)
        pipe.expire(f"ips:{slug}:country.{clickData.country}", self.ttl_seconds)
        if clickData.referrer:
            pipe.expire(f"ips:{slug}:referrer.{clickData.referrer}", self.ttl_seconds)

        try:
            pipe.execute()
        except Exception as e:
            raise e

    def pull(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get the parsed data of a slug from the cache
        :param slug: Slug of the URL
        :return: Parsed data of the slug
        """
        if not self.check_exists(slug):
            return None

        cnt_keys: str = f"counts:{slug}"
        meta_keys: str = f"meta:{slug}"

        counts = self.r.hgetall(cnt_keys)
        meta = self.r.hgetall(meta_keys)

        # Fetch all the IP sets
        ip_pattern: str = f"ips:{slug}:*"
        ip_keys = list(self.r.scan_iter(ip_pattern))

        pipe: Pipeline = self.r.pipeline()
        for k in ip_keys:
            pipe.smembers(k)
        ip_sets = pipe.execute()

        # parse incements and meta data
        inc: Dict[str, int] = {}

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
        # parse sets to lists
        for k, v in zip(ip_keys, ip_sets):
            key: List[str] = k.decode().split(f"ips:{slug}:")[1].split(".")

            if len(key) < 2:
                by_dim[key[0]] = [ip.decode() for ip in v]
                continue
            if key[0] not in by_dim:
                by_dim[key[0]] = {}
            by_dim[key[0]][key[1]] = [ip.decode() for ip in v]

        # delte the data of the slug
        self.r.delete(cnt_keys, meta_keys, *ip_keys)
        self.r.srem("slugs", slug)

        return {
            "slug": slug,
            "inc": inc,
            "set": set_,
            "addtoset": by_dim,
        }

    def pull_all(self) -> List[Dict[str, Any]]:
        """
        Pull the data of all the slugs in the cache
        :return: List of parsed data of all the slugs
        """
        results: List[dict] = []
        # Grab all queued slugs at once
        slugs = self.r.smembers("slugs")

        for raw in slugs:
            slug: str = raw.decode()
            parsed = self.pull(slug)
            if parsed:
                results.append(parsed)
            else:
                # no data to push, remove it from `slugs`
                self.r.srem("slugs", slug)

        return results

    def check_exists(self, slug: str) -> bool:
        """
        Check if the slug exists in the cache
        :param slug: Slug of the URL
        :return: True if the slug exists, False otherwise
        """
        return self.r.sismember("slugs", slug)
