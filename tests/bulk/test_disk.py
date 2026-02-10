"""Tests for DiskPool."""

import threading
from typing import NamedTuple
from unittest.mock import patch

import pytest

from internetarchive.bulk.disk import DEFAULT_MARGIN, DiskPool


class DiskUsage(NamedTuple):
    total: float
    used: float
    free: float


class TestDiskPool:
    def test_single_disk_route(self, tmp_path):
        pool = DiskPool([str(tmp_path)])
        result = pool.route(1024)
        assert result == str(tmp_path)

    def test_no_paths_raises(self):
        with pytest.raises(ValueError, match="at least one path"):
            DiskPool([])

    def test_no_check_space(self, tmp_path):
        p1 = str(tmp_path / "disk1")
        p2 = str(tmp_path / "disk2")
        pool = DiskPool([p1, p2], check_space=False)
        # Always returns first path when check disabled
        assert pool.route(999999999999) == p1

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_picks_disk_with_most_space(self, mock_usage):
        mock_usage.side_effect = lambda p: {
            "/disk1": DiskUsage(100e9, 80e9, 20e9),
            "/disk2": DiskUsage(100e9, 50e9, 50e9),
        }[p]

        pool = DiskPool(["/disk1", "/disk2"])
        result = pool.route(1024)
        assert result == "/disk2"

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_returns_none_when_full(self, mock_usage):
        mock_usage.return_value = DiskUsage(
            100e9, 99.5e9, 0.5e9
        )  # 500MB free, less than 1GB margin

        pool = DiskPool(["/disk1"])
        result = pool.route(1024)
        assert result is None

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_reservation_tracking(self, mock_usage):
        mock_usage.return_value = DiskUsage(
            100e9, 90e9, 10e9
        )  # 10GB free

        pool = DiskPool(["/disk1"], margin=DEFAULT_MARGIN)
        # Reserve 8GB — should leave ~1GB free (just margin)
        result = pool.route(int(8e9))
        assert result == "/disk1"

        # Now try another 1GB — should fail (only ~1GB margin left)
        result2 = pool.route(int(1e9))
        assert result2 is None

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_release_frees_reservation(self, mock_usage):
        mock_usage.return_value = DiskUsage(
            100e9, 90e9, 10e9
        )  # 10GB free

        pool = DiskPool(["/disk1"])
        estimated = int(5e9)
        path = pool.route(estimated)
        assert path == "/disk1"

        # Release the reservation
        pool.release("/disk1", estimated)

        # Should be able to route again
        result = pool.route(estimated)
        assert result == "/disk1"

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_os_error_skips_disk(self, mock_usage):
        mock_usage.side_effect = OSError("disk not mounted")
        pool = DiskPool(["/unmounted"])
        assert pool.route(1024) is None

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_concurrent_routing(self, mock_usage):
        mock_usage.return_value = DiskUsage(
            100e9, 50e9, 50e9
        )  # 50GB free

        pool = DiskPool(["/disk1"])
        results = []
        errors = []

        def route_and_collect():
            try:
                r = pool.route(int(1e9))
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=route_and_collect)
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(r == "/disk1" for r in results)

    @patch("internetarchive.bulk.disk.shutil.disk_usage")
    def test_custom_margin(self, mock_usage):
        mock_usage.return_value = DiskUsage(
            100e9, 97e9, 3e9
        )  # 3GB free

        # With 2GB margin, 1GB download should work
        pool = DiskPool(["/disk1"], margin=int(2e9))
        assert pool.route(int(1e9)) == "/disk1"

        # With 5GB margin, should fail
        pool2 = DiskPool(["/disk1"], margin=int(5e9))
        assert pool2.route(int(1e9)) is None

    def test_release_below_zero(self):
        """Release more than reserved should clamp to zero."""
        pool = DiskPool(["/disk1"], check_space=False)
        pool.release("/disk1", int(1e9))
        # After releasing more than reserved, route should still work
        assert pool.route() == "/disk1"
