"""
ExportService — data export for v2 stats.

Composes StatsService for data, then delegates serialisation to the
injected formatter registry.  Returns an ExportResult so the route can
build the file response without any framework coupling here.

Adding a new export format never requires touching this file:
create a class implementing ExportFormatter and register it in
default_formatters() (services/export/formatters.py).

The legacy v1 export (GET /export/<code>/<format> page) continues to use
utils/export_utils.py directly — that path is unaffected by this service.
"""

from __future__ import annotations

from errors import ValidationError
from schemas.dto.requests.stats import ExportQuery
from schemas.enums.stats import StatsScope
from schemas.results import ExportResult
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
        query: ExportQuery,
        owner_id: str | None,
    ) -> ExportResult:
        """Retrieve stats and serialise them in the requested format.

        Args:
            query:    Validated ExportQuery DTO with format and stats parameters.
            owner_id: String user ID for scope=all, or None.

        Raises:
            ValidationError: Unknown format.
            Propagates all errors from StatsService.query().
        """
        fmt = query.format
        if fmt not in self._formatters:
            raise ValidationError(
                f"invalid format — must be one of: {', '.join(sorted(self._formatters))}"
            )

        data = await self._stats.query(query, owner_id)

        formatter = self._formatters[fmt]
        content = formatter.serialize(data)

        log.info(
            "export_generated",
            format=fmt,
            scope=query.scope,
            short_code=query.short_code if query.scope == StatsScope.ANON else None,
            size_bytes=len(content),
        )
        return ExportResult(
            content=content, mimetype=formatter.mimetype, filename=formatter.filename
        )
