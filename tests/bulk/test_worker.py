"""Tests for the worker interface."""

from threading import Event

import pytest

from internetarchive.bulk.worker import BaseWorker, WorkerResult


class DummyWorker(BaseWorker):
    """Minimal worker implementation for testing the contract."""

    def execute(self, identifier, job, cancel_event):
        return WorkerResult(
            success=True,
            identifier=identifier,
            extra={"key": "value"},
        )


class FailingWorker(BaseWorker):
    """Worker that always fails."""

    def execute(self, identifier, job, cancel_event):
        return WorkerResult(
            success=False,
            identifier=identifier,
            error="something went wrong",
            retry=False,
        )


def test_worker_result_defaults():
    r = WorkerResult(success=True, identifier="test-item")
    assert r.success is True
    assert r.identifier == "test-item"
    assert r.error is None
    assert r.backoff is False
    assert r.retry is True
    assert r.extra == {}


def test_worker_result_failure():
    r = WorkerResult(
        success=False,
        identifier="bad-item",
        error="HTTP 503",
        backoff=True,
        retry=True,
    )
    assert r.success is False
    assert r.error == "HTTP 503"
    assert r.backoff is True


def test_dummy_worker_execute():
    worker = DummyWorker()
    result = worker.execute("foo", {"op": "download"}, Event())
    assert result.success is True
    assert result.identifier == "foo"
    assert result.extra == {"key": "value"}


def test_failing_worker_execute():
    worker = FailingWorker()
    result = worker.execute("bar", {"op": "download"}, Event())
    assert result.success is False
    assert result.error == "something went wrong"
    assert result.retry is False


def test_worker_is_abstract():
    """Cannot instantiate BaseWorker directly."""
    with pytest.raises(TypeError):
        BaseWorker()
