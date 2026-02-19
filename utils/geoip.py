import threading
import geoip2.database
import geoip2.errors
import maxminddb
from utils.logger import get_logger

log = get_logger(__name__)


class GeoIPService:
    """Manages GeoIP database readers as lazily-initialized singletons."""

    _COUNTRY_DB = "misc/GeoLite2-Country.mmdb"
    _CITY_DB = "misc/GeoLite2-City.mmdb"

    def __init__(self):
        self._country_reader = None
        self._city_reader = None
        self._country_loaded = False
        self._city_loaded = False
        self._lock = threading.Lock()

    def _get_country_reader(self):
        if not self._country_loaded:
            with self._lock:
                if not self._country_loaded:
                    try:
                        self._country_reader = geoip2.database.Reader(self._COUNTRY_DB)
                    except (OSError, maxminddb.InvalidDatabaseError) as e:
                        log.warning(
                            "geoip_country_db_unavailable",
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        self._country_reader = None
                    self._country_loaded = True
        return self._country_reader

    def _get_city_reader(self):
        if not self._city_loaded:
            with self._lock:
                if not self._city_loaded:
                    try:
                        self._city_reader = geoip2.database.Reader(self._CITY_DB)
                    except (OSError, maxminddb.InvalidDatabaseError) as e:
                        log.warning(
                            "geoip_city_db_unavailable",
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        self._city_reader = None
                    self._city_loaded = True
        return self._city_reader

    def get_country(self, ip_address: str) -> str:
        reader = self._get_country_reader()
        if reader is None:
            return "Unknown"
        try:
            return reader.country(ip_address).country.name or "Unknown"
        except (
            geoip2.errors.AddressNotFoundError,
            ValueError,
            maxminddb.InvalidDatabaseError,
        ):
            return "Unknown"

    def get_city(self, ip_address: str) -> str | None:
        reader = self._get_city_reader()
        if reader is None:
            return None
        try:
            return reader.city(ip_address).city.name
        except (
            geoip2.errors.AddressNotFoundError,
            ValueError,
            maxminddb.InvalidDatabaseError,
        ):
            return None


geoip = GeoIPService()
