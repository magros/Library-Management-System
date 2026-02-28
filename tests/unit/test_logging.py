"""
Unit tests for app.core.logging – JSONFormatter, context variables, logger factory.
"""
import json
import logging
from unittest.mock import patch

import pytest

from app.core.logging import (
    JSONFormatter,
    get_logger,
    request_id_ctx,
    current_user_id_ctx,
    setup_logging,
)


class TestJSONFormatter:
    def _make_record(self, message="test msg", level=logging.INFO, name="test"):
        logger = logging.getLogger(name)
        record = logger.makeRecord(
            name=name,
            level=level,
            fn="test.py",
            lno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        return record

    def test_output_is_valid_json(self):
        formatter = JSONFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_required_fields(self):
        formatter = JSONFormatter()
        record = self._make_record("hello")
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "message" in parsed
        assert parsed["message"] == "hello"

    def test_level_name(self):
        formatter = JSONFormatter()
        record = self._make_record(level=logging.WARNING)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "WARNING"

    def test_logger_name(self):
        formatter = JSONFormatter()
        record = self._make_record(name="services.auth")
        parsed = json.loads(formatter.format(record))
        assert parsed["logger"] == "services.auth"

    def test_includes_request_id_when_set(self):
        formatter = JSONFormatter()
        token = request_id_ctx.set("req-abc-123")
        try:
            record = self._make_record()
            parsed = json.loads(formatter.format(record))
            assert parsed["request_id"] == "req-abc-123"
        finally:
            request_id_ctx.reset(token)

    def test_excludes_request_id_when_not_set(self):
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "request_id" not in parsed

    def test_includes_user_id_when_set(self):
        formatter = JSONFormatter()
        token = current_user_id_ctx.set("user-42")
        try:
            record = self._make_record()
            parsed = json.loads(formatter.format(record))
            assert parsed["user_id"] == "user-42"
        finally:
            current_user_id_ctx.reset(token)

    def test_excludes_user_id_when_not_set(self):
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "user_id" not in parsed

    def test_includes_extra_data(self):
        formatter = JSONFormatter()
        record = self._make_record()
        record.extra_data = {"loan_id": "loan-99", "action": "approve"}
        parsed = json.loads(formatter.format(record))
        assert parsed["loan_id"] == "loan-99"
        assert parsed["action"] == "approve"

    def test_includes_exception_info(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            record = self._make_record()
            record.exc_info = sys.exc_info()
            parsed = json.loads(formatter.format(record))
            assert "exception" in parsed
            assert "ValueError" in parsed["exception"]

    def test_timestamp_is_iso_format(self):
        formatter = JSONFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        # ISO 8601 timestamps contain "T" and end with timezone info
        assert "T" in parsed["timestamp"]


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_same_name_returns_same_logger(self):
        l1 = get_logger("same.name")
        l2 = get_logger("same.name")
        assert l1 is l2

    def test_different_names(self):
        l1 = get_logger("a.module")
        l2 = get_logger("b.module")
        assert l1 is not l2


class TestSetupLogging:
    def test_setup_does_not_raise(self):
        # Just verify it runs without errors
        setup_logging()

    def test_root_logger_has_handler(self):
        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_handler_uses_json_formatter(self):
        setup_logging()
        root = logging.getLogger()
        json_formatters = [
            h for h in root.handlers
            if isinstance(h.formatter, JSONFormatter)
        ]
        assert len(json_formatters) > 0


class TestContextVariables:
    def test_request_id_default_is_none(self):
        assert request_id_ctx.get() is None

    def test_current_user_id_default_is_none(self):
        assert current_user_id_ctx.get() is None

    def test_set_and_reset_request_id(self):
        token = request_id_ctx.set("req-test")
        assert request_id_ctx.get() == "req-test"
        request_id_ctx.reset(token)
        assert request_id_ctx.get() is None

    def test_set_and_reset_user_id(self):
        token = current_user_id_ctx.set("uid-test")
        assert current_user_id_ctx.get() == "uid-test"
        current_user_id_ctx.reset(token)
        assert current_user_id_ctx.get() is None

