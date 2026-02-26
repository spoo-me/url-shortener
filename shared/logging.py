"""
Logging utilities for spoo.me — framework-agnostic re-exports.

Re-exports from utils.logger and utils.logging_config so that FastAPI
code can import from shared.logging without depending on Flask modules.

During migration (Phases 4–15) both this module and utils.logger coexist;
at Phase 16 cleanup the utils versions can be removed.
"""

from utils.logger import get_logger, hash_ip, log_with_context, should_sample
from utils.logging_config import (
    SAMPLING_RATES,
    configure_structlog,
    setup_logging,
)

__all__ = [
    "get_logger",
    "hash_ip",
    "log_with_context",
    "should_sample",
    "SAMPLING_RATES",
    "configure_structlog",
    "setup_logging",
]
