"""Shared helpers for schema model tests."""

from datetime import datetime, timezone

from bson import ObjectId


def now():
    return datetime.now(timezone.utc)


def oid():
    return ObjectId()
