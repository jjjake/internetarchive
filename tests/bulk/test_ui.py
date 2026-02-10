"""Tests for UIEvent, UIHandler, and PlainUI."""

import io

import pytest

from internetarchive.bulk.ui import PlainUI, UIEvent, UIHandler, _format_bytes


class TestUIEvent:
    def test_defaults(self):
        e = UIEvent(kind="job_started")
        assert e.kind == "job_started"
        assert e.seq == 0
        assert e.total == 0
        assert e.identifier == ""
        assert e.extra == {}

    def test_with_values(self):
        e = UIEvent(
            kind="job_completed",
            seq=5,
            total=100,
            identifier="foo",
            extra={"bytes": 1024},
            elapsed=3.5,
        )
        assert e.seq == 5
        assert e.extra["bytes"] == 1024


class TestUIHandler:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            UIHandler()


class TestPlainUI:
    def _capture(self):
        buf = io.StringIO()
        return buf, PlainUI(file=buf)

    def test_job_started(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_started",
            seq=1,
            total=100,
            identifier="foo-item",
            worker=2,
        ))
        output = buf.getvalue()
        assert "foo-item: started (worker 2)" in output
        assert "[1/100]" in output

    def test_job_completed_with_bytes(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_completed",
            seq=1,
            total=100,
            identifier="foo-item",
            extra={"bytes": 10_485_760},
            elapsed=44,
        ))
        output = buf.getvalue()
        assert "foo-item: completed" in output
        assert "10.0 MB" in output
        assert "44s" in output

    def test_job_completed_no_extra(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_completed",
            seq=1,
            total=100,
            identifier="foo-item",
        ))
        output = buf.getvalue()
        assert "foo-item: completed" in output

    def test_job_failed(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_failed",
            seq=2,
            total=100,
            identifier="bar-item",
            error="HTTP 503",
            retry=1,
            max_retries=3,
        ))
        output = buf.getvalue()
        assert "bar-item: failed: HTTP 503" in output
        assert "(retry 1/3)" in output

    def test_job_skipped(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="job_skipped",
            seq=1,
            total=100,
            identifier="done-item",
        ))
        output = buf.getvalue()
        assert "done-item: skipped (already completed)" in output

    def test_backoff_start(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="backoff_start",
            error="all disks full, waiting for in-flight jobs",
        ))
        output = buf.getvalue()
        assert "backoff:" in output
        assert "all disks full" in output

    def test_backoff_end(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(kind="backoff_end"))
        output = buf.getvalue()
        assert "backoff: resuming" in output

    def test_progress(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(
            kind="progress",
            extra={"completed": 50, "failed": 2, "pending": 48},
        ))
        output = buf.getvalue()
        assert "50 completed" in output
        assert "2 failed" in output
        assert "48 pending" in output

    def test_timestamp_in_output(self):
        buf, ui = self._capture()
        ui.handle(UIEvent(kind="job_started", seq=1, total=1,
                          identifier="x"))
        output = buf.getvalue()
        # Should contain timestamp like [HH:MM:SS]
        assert output.startswith("[")
        assert "]" in output


class TestFormatBytes:
    def test_bytes(self):
        assert _format_bytes(500) == "500 B"
        assert _format_bytes(1024) == "1.0 KB"
        assert _format_bytes(1024 * 1024) == "1.0 MB"
        assert _format_bytes(1024 * 1024 * 1024) == "1.0 GB"
