"""
ExportService — data export for v2 stats.

Composes StatsService for data, then delegates serialisation to the
injected formatter registry.  Returns raw bytes + HTTP metadata so the
route can build the file response without any framework coupling here.

Adding a new export format never requires touching this file:
create a class implementing ExportFormatter and register it in
default_formatters() (services/export/formatters.py).

The legacy v1 export (GET /export/<code>/<format> page) continues to use
utils/export_utils.py directly — that path is unaffected by this service.
"""

from __future__ import annotations

from datetime import datetime

from errors import ValidationError
from schemas.dto.requests.stats import StatsScope
from services.export.protocol import ExportFormatter
from services.stats_service import StatsService
from shared.logging import get_logger

log = get_logger(__name__)


class ExportService:
    """Export service for v2 stats.

    Args:
        stats_service: StatsService instance used to retrieve analytics data.
        formatters:    Registry mapping format name → ExportFormatter instance.
                        Inject via ``default_formatters()`` at the composition root.
    """

    def __init__(
        self,
        stats_service: StatsService,
        formatters: dict[str, ExportFormatter],
    ) -> None:
        self._stats = stats_service
        self._formatters = formatters

    async def export(
        self,
        fmt: str,
        owner_id: str | None,
        scope: str,
        short_code: str | None,
        start_date: datetime | None,
        end_date: datetime | None,
        filters: dict[str, list[str]],
        group_by: list[str],
        metrics: list[str],
        tz_name: str,
    ) -> tuple[bytes, str, str]:
        """Retrieve stats and serialise them in the requested format.

        Args:
            fmt:        Export format — one of the keys in the injected formatters dict.
            owner_id:   String user ID for scope=all, or None.
            scope:      ``"all"`` | ``"anon"``
            short_code: Required when scope=anon.
            start_date: UTC start of the time window.
            end_date:   UTC end of the time window.
            filters:    Dimension filters.
            group_by:   Aggregation dimensions.
            metrics:    Metrics to export.
            tz_name:    IANA timezone name.

        Returns:
            (content_bytes, mimetype, filename)

        Raises:
            ValidationError: Unknown format.
            Propagates all errors from StatsService.query().
        """
        if fmt not in self._formatters:
            raise ValidationError(
                f"invalid format — must be one of: {', '.join(sorted(self._formatters))}"
            )

        data = await self._stats.query(
            owner_id=owner_id,
            scope=scope,
            short_code=short_code,
            start_date=start_date,
            end_date=end_date,
            filters=filters,
            group_by=group_by,
            metrics=metrics,
            tz_name=tz_name,
        )

        formatter = self._formatters[fmt]
        content = formatter.serialize(data)

        log.info(
            "export_generated",
            format=fmt,
            scope=scope,
            short_code=short_code if scope == StatsScope.ANON else None,
            size_bytes=len(content),
        )
        return content, formatter.mimetype, formatter.filename
