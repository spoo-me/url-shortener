"""Unit tests for common response DTOs."""

from __future__ import annotations

from schemas.dto.responses.common import ErrorResponse, HealthResponse


class TestErrorResponse:
    def test_minimal(self):
        d = ErrorResponse(error="not found", error_code="not_found").model_dump(
            exclude_none=True
        )
        assert d == {"error": "not found", "error_code": "not_found"}

    def test_with_field_and_details(self):
        r = ErrorResponse(
            error="bad input",
            error_code="validation_error",
            field="email",
            details={"hint": "must be valid email"},
        )
        d = r.model_dump()
        assert d["field"] == "email"
        assert d["details"] == {"hint": "must be valid email"}

    def test_without_optional_fields(self):
        d = ErrorResponse(error="fail", error_code="err").model_dump()
        assert d["field"] is None
        assert d["details"] is None


class TestHealthResponse:
    def test_serialization(self):
        r = HealthResponse(status="healthy", checks={"mongodb": "ok", "redis": "ok"})
        d = r.model_dump()
        assert d["status"] == "healthy"
        assert d["checks"]["mongodb"] == "ok"
