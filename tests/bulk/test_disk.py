from __future__ import annotations

from unittest.mock import patch

import pytest

from internetarchive.bulk.disk import DiskPool, parse_size

# ---------------------------------------------------------------------------
# Helper: fake statvfs
# ---------------------------------------------------------------------------

class FakeStatvfs:
    """Minimal os.statvfs result with controllable free space."""

    def __init__(self, free_bytes: int, block_size: int = 4096):
        self.f_frsize = block_size
        self.f_bavail = free_bytes // block_size


def make_statvfs_map(mapping: dict[str, int]):
    """Return a callable that maps directory paths to fake statvfs objects.

    Args:
        mapping: {path: free_bytes} dictionary.
    """
    def _fake_statvfs(path: str) -> FakeStatvfs:
        for dir_path, free in mapping.items():
            if path == dir_path:
                return FakeStatvfs(free)
        raise OSError(f"No fake statvfs for {path}")
    return _fake_statvfs


# ===========================================================================
# parse_size tests
# ===========================================================================

class TestParseSize:
    """Tests for the parse_size helper function."""

    def test_plain_bytes(self):
        assert parse_size("1024") == 1024

    def test_kilobytes(self):
        assert parse_size("100K") == 100 * 1024

    def test_kilobytes_lower(self):
        assert parse_size("100k") == 100 * 1024

    def test_megabytes(self):
        assert parse_size("500M") == 500 * 1024**2

    def test_gigabytes(self):
        assert parse_size("1G") == 1 * 1024**3

    def test_terabytes(self):
        assert parse_size("2T") == 2 * 1024**4

    def test_with_b_suffix(self):
        """Trailing 'B' (e.g. '1GB') is accepted."""
        assert parse_size("1GB") == 1 * 1024**3

    def test_case_insensitive(self):
        assert parse_size("500m") == 500 * 1024**2
        assert parse_size("1g") == 1 * 1024**3
        assert parse_size("2t") == 2 * 1024**4

    def test_with_trailing_b_various(self):
        assert parse_size("500MB") == 500 * 1024**2
        assert parse_size("100KB") == 100 * 1024
        assert parse_size("2TB") == 2 * 1024**4

    def test_invalid_empty(self):
        with pytest.raises(ValueError, match="Invalid size string"):
            parse_size("")

    def test_invalid_letters(self):
        with pytest.raises(ValueError, match="Invalid size string"):
            parse_size("abc")

    def test_invalid_no_number(self):
        with pytest.raises(ValueError, match="Invalid size string"):
            parse_size("G")

    def test_invalid_unknown_suffix(self):
        with pytest.raises(ValueError, match="Invalid size string"):
            parse_size("100X")


# ===========================================================================
# DiskPool tests
# ===========================================================================

class TestDiskPool:
    """Tests for DiskPool disk-space monitoring and routing."""

    def test_route_to_first_disk(self):
        """Route returns the first disk that has enough space."""
        mapping = {"/disk1": 10 * 1024**3, "/disk2": 10 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1", "/disk2"])
            dest = pool.route(1 * 1024**3)
            assert dest == "/disk1"

    def test_overflow_to_second_disk(self):
        """When the first disk is too full, route to the second."""
        mapping = {"/disk1": 500 * 1024**2, "/disk2": 10 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1", "/disk2"])
            dest = pool.route(1 * 1024**3)
            assert dest == "/disk2"

    def test_no_space_returns_none(self):
        """If no disk has enough space, return None."""
        mapping = {"/disk1": 500 * 1024**2, "/disk2": 500 * 1024**2}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1", "/disk2"])
            dest = pool.route(1 * 1024**3)
            assert dest is None

    def test_reservations_prevent_overcommit(self):
        """Reservations are subtracted from available space."""
        # 3 GB free on disk1 with default 1 GB margin => 2 GB usable.
        # Two 1 GB reservations should fill it, third should overflow.
        mapping = {"/disk1": 3 * 1024**3, "/disk2": 10 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1", "/disk2"])
            d1 = pool.route(1 * 1024**3)
            assert d1 == "/disk1"
            d2 = pool.route(1 * 1024**3)
            assert d2 == "/disk1"
            # Third reservation pushes past available.
            d3 = pool.route(1 * 1024**3)
            assert d3 == "/disk2"

    def test_release_frees_reservation(self):
        """release() frees a reservation so space becomes available again."""
        mapping = {"/disk1": 3 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1"])
            size = 1 * 1024**3
            pool.route(size)
            pool.route(size)
            # Now 2 GB reserved, only margin left.
            assert pool.route(size) is None
            # Release one reservation.
            pool.release("/disk1", size)
            assert pool.route(size) == "/disk1"

    def test_mark_full_removes_disk(self):
        """mark_full() removes a disk from routing entirely."""
        mapping = {"/disk1": 10 * 1024**3, "/disk2": 10 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1", "/disk2"])
            pool.mark_full("/disk1")
            dest = pool.route(1 * 1024**3)
            assert dest == "/disk2"

    def test_available_bytes_calculation(self):
        """available() returns free bytes minus margin and reservations."""
        mapping = {"/disk1": 5 * 1024**3}
        margin = 1 * 1024**3
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1"], margin=margin)
            # No reservations: 5G - 1G margin = 4G.
            assert pool.available("/disk1") == 4 * 1024**3
            # Reserve 1G.
            pool.route(1 * 1024**3)
            assert pool.available("/disk1") == 3 * 1024**3

    def test_unknown_size_uses_double_margin(self):
        """When est_bytes is None, route uses 2*margin as the estimate."""
        margin = 1 * 1024**3
        # 3G free, 1G margin, 2G for unknown estimate => just barely fits.
        mapping = {"/disk1": 3 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1"], margin=margin)
            dest = pool.route(None)
            assert dest == "/disk1"

    def test_unknown_size_too_large(self):
        """When est_bytes is None and 2*margin exceeds available, overflow."""
        margin = 1 * 1024**3
        # 2.5G free, margin=1G => 1.5G available, but unknown needs 2G.
        free = int(2.5 * 1024**3)
        mapping = {"/disk1": free}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1"], margin=margin)
            dest = pool.route(None)
            assert dest is None

    def test_disabled_mode_bypasses_checks(self):
        """When disabled=True, always return the first destdir."""
        mapping = {"/disk1": 0, "/disk2": 10 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1", "/disk2"], disabled=True)
            dest = pool.route(100 * 1024**3)
            assert dest == "/disk1"

    def test_in_flight_tracking(self):
        """in_flight_count() tracks how many items are routed to a disk."""
        mapping = {"/disk1": 100 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1"])
            assert pool.in_flight_count("/disk1") == 0
            pool.route(1 * 1024**3)
            assert pool.in_flight_count("/disk1") == 1
            pool.route(2 * 1024**3)
            assert pool.in_flight_count("/disk1") == 2
            pool.release("/disk1", 1 * 1024**3)
            assert pool.in_flight_count("/disk1") == 1

    def test_in_flight_count_unknown_disk(self):
        """in_flight_count() returns 0 for an unknown disk."""
        mapping = {"/disk1": 10 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1"])
            assert pool.in_flight_count("/unknown") == 0

    def test_release_does_not_go_negative(self):
        """Releasing more than reserved should not produce negative values."""
        mapping = {"/disk1": 10 * 1024**3}
        with patch("os.statvfs", side_effect=make_statvfs_map(mapping)):
            pool = DiskPool(["/disk1"])
            pool.route(1 * 1024**3)
            pool.release("/disk1", 1 * 1024**3)
            # Extra release should clamp at zero.
            pool.release("/disk1", 1 * 1024**3)
            assert pool.available("/disk1") == 10 * 1024**3 - 1024**3
