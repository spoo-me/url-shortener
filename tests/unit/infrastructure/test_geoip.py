"""Unit tests for GeoIPService."""

from unittest.mock import MagicMock

import geoip2.errors

from infrastructure.geoip import GeoIPService


class TestGeoIPService:
    async def test_get_country_returns_unknown_when_db_missing(self):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        result = await svc.get_country("1.2.3.4")
        assert result == "Unknown"

    async def test_get_city_returns_none_when_db_missing(self):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        result = await svc.get_city("1.2.3.4")
        assert result is None

    async def test_get_country_returns_unknown_on_lookup_error(self, mocker):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        fake_reader = MagicMock()
        fake_reader.country.side_effect = geoip2.errors.AddressNotFoundError(
            "not found"
        )
        svc._country_reader = fake_reader
        svc._country_loaded = True
        result = await svc.get_country("1.2.3.4")
        assert result == "Unknown"

    async def test_get_city_returns_none_on_lookup_error(self, mocker):
        svc = GeoIPService("nonexistent.mmdb", "nonexistent.mmdb")
        fake_reader = MagicMock()
        fake_reader.city.side_effect = geoip2.errors.AddressNotFoundError("not found")
        svc._city_reader = fake_reader
        svc._city_loaded = True
        result = await svc.get_city("1.2.3.4")
        assert result is None
