from __future__ import annotations

from pathlib import Path

import pytest

from internetarchive.bulk.worker import BaseWorker, VerifyResult, WorkerResult


class TestWorkerResult:
    """Tests for WorkerResult dataclass."""

    def test_success_result(self):
        result = WorkerResult(
            success=True,
            identifier="test-item",
            bytes_transferred=1024,
            files_ok=5,
            files_skipped=1,
            files_failed=0,
            error=None,
        )
        assert result.success is True
        assert result.identifier == "test-item"
        assert result.bytes_transferred == 1024
        assert result.files_ok == 5
        assert result.files_skipped == 1
        assert result.files_failed == 0
        assert result.error is None

    def test_failure_result(self):
        result = WorkerResult(
            success=False,
            identifier="broken-item",
            bytes_transferred=0,
            files_ok=0,
            files_skipped=0,
            files_failed=3,
            error="Connection refused",
        )
        assert result.success is False
        assert result.identifier == "broken-item"
        assert result.bytes_transferred == 0
        assert result.files_ok == 0
        assert result.files_failed == 3
        assert result.error == "Connection refused"

    def test_default_values(self):
        result = WorkerResult(
            success=True,
            identifier="defaults-item",
        )
        assert result.bytes_transferred == 0
        assert result.files_ok == 0
        assert result.files_skipped == 0
        assert result.files_failed == 0
        assert result.error is None

    def test_partial_transfer_on_failure(self):
        """A failed result can still have some bytes transferred."""
        result = WorkerResult(
            success=False,
            identifier="partial-item",
            bytes_transferred=512,
            files_ok=2,
            files_skipped=0,
            files_failed=1,
            error="Timeout on third file",
        )
        assert result.success is False
        assert result.bytes_transferred == 512
        assert result.files_ok == 2
        assert result.files_failed == 1


class TestVerifyResult:
    """Tests for VerifyResult dataclass."""

    def test_complete_verification(self):
        result = VerifyResult(
            identifier="verified-item",
            complete=True,
            files_expected=10,
            files_found=10,
            files_missing=[],
            files_corrupted=[],
        )
        assert result.identifier == "verified-item"
        assert result.complete is True
        assert result.files_expected == 10
        assert result.files_found == 10
        assert result.files_missing == []
        assert result.files_corrupted == []

    def test_incomplete_verification(self):
        result = VerifyResult(
            identifier="incomplete-item",
            complete=False,
            files_expected=5,
            files_found=3,
            files_missing=["file_a.txt", "file_b.txt"],
            files_corrupted=["file_c.txt"],
        )
        assert result.complete is False
        assert result.files_expected == 5
        assert result.files_found == 3
        assert result.files_missing == ["file_a.txt", "file_b.txt"]
        assert result.files_corrupted == ["file_c.txt"]

    def test_default_values(self):
        result = VerifyResult(
            identifier="defaults-item",
            complete=True,
            files_expected=0,
            files_found=0,
        )
        assert result.files_missing == []
        assert result.files_corrupted == []

    def test_mutable_defaults_not_shared(self):
        """Ensure default list fields are not shared between instances."""
        r1 = VerifyResult(
            identifier="item-1",
            complete=True,
            files_expected=0,
            files_found=0,
        )
        r2 = VerifyResult(
            identifier="item-2",
            complete=True,
            files_expected=0,
            files_found=0,
        )
        r1.files_missing.append("leaked.txt")
        assert r2.files_missing == []


class TestBaseWorker:
    """Tests for BaseWorker ABC."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseWorker()  # type: ignore[abstract]

    def test_concrete_worker_implements_interface(self, tmp_path):
        """A concrete subclass can be instantiated and called."""

        class FakeWorker(BaseWorker):
            def estimate_size(self, identifier: str) -> int | None:
                if identifier == "unknown":
                    return None
                return 42

            def execute(
                self, identifier: str, destdir: Path
            ) -> WorkerResult:
                return WorkerResult(
                    success=True,
                    identifier=identifier,
                    bytes_transferred=42,
                    files_ok=1,
                )

            def verify(
                self, identifier: str, destdir: Path
            ) -> VerifyResult:
                return VerifyResult(
                    identifier=identifier,
                    complete=True,
                    files_expected=1,
                    files_found=1,
                )

        worker = FakeWorker()

        # estimate_size
        assert worker.estimate_size("test-item") == 42
        assert worker.estimate_size("unknown") is None

        # execute
        result = worker.execute("test-item", tmp_path)
        assert isinstance(result, WorkerResult)
        assert result.success is True
        assert result.identifier == "test-item"
        assert result.bytes_transferred == 42

        # verify
        vresult = worker.verify("test-item", tmp_path)
        assert isinstance(vresult, VerifyResult)
        assert vresult.complete is True
        assert vresult.identifier == "test-item"

    def test_partial_implementation_fails(self):
        """Missing abstract methods should prevent instantiation."""

        class PartialWorker(BaseWorker):
            def estimate_size(self, identifier: str) -> int | None:
                return None

        with pytest.raises(TypeError):
            PartialWorker()  # type: ignore[abstract]
