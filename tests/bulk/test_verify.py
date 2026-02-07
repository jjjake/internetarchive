#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2024 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see
# <http://www.gnu.org/licenses/>.

"""Tests for DownloadWorker.verify() functionality.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from internetarchive.bulk.worker import VerifyResult
from internetarchive.workers.download import DownloadWorker


def _mock_session_factory(item):
    """Return a factory that yields a mock session whose
    get_item() always returns *item*."""
    def factory():
        session = MagicMock()
        session.get_item.return_value = item
        return session
    return factory


# ---------------------------------------------------------
# Complete item (all files present)
# ---------------------------------------------------------


class TestVerifyCompleteItem:
    """All expected files are present on disk."""

    def test_single_file_complete(self, tmp_path):
        """One file expected, one file on disk."""
        item = MagicMock()
        item.files = [{"name": "file1.txt"}]

        item_dir = tmp_path / "test-item"
        item_dir.mkdir()
        (item_dir / "file1.txt").write_bytes(b"hello")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("test-item", str(tmp_path))

        assert isinstance(result, VerifyResult)
        assert result.complete is True
        assert result.files_expected == 1
        assert result.files_found == 1
        assert result.files_missing == []

    def test_multiple_files_all_present(self, tmp_path):
        """Several files expected, all present on disk."""
        item = MagicMock()
        item.files = [
            {"name": "readme.txt"},
            {"name": "data.csv"},
            {"name": "image.jpg"},
        ]

        item_dir = tmp_path / "multi-item"
        item_dir.mkdir()
        (item_dir / "readme.txt").write_text("readme")
        (item_dir / "data.csv").write_text("a,b,c")
        (item_dir / "image.jpg").write_bytes(b"\xff\xd8")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("multi-item", str(tmp_path))

        assert result.complete is True
        assert result.files_expected == 3
        assert result.files_found == 3
        assert result.files_missing == []

    def test_complete_with_path_destdir(self, tmp_path):
        """destdir can be a Path object, not just a string."""
        item = MagicMock()
        item.files = [{"name": "doc.pdf"}]

        item_dir = tmp_path / "path-item"
        item_dir.mkdir()
        (item_dir / "doc.pdf").write_bytes(b"%PDF")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("path-item", Path(tmp_path))

        assert result.complete is True
        assert result.files_found == 1


# ---------------------------------------------------------
# Missing files
# ---------------------------------------------------------


class TestVerifyMissingFiles:
    """One or more expected files are missing from disk."""

    def test_single_file_missing(self, tmp_path):
        """One file expected but not on disk."""
        item = MagicMock()
        item.files = [{"name": "missing.txt"}]

        item_dir = tmp_path / "test-item"
        item_dir.mkdir()
        # Do not create the file.

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("test-item", str(tmp_path))

        assert result.complete is False
        assert result.files_expected == 1
        assert result.files_found == 0
        assert result.files_missing == ["missing.txt"]

    def test_partial_files_missing(self, tmp_path):
        """Multiple files expected, some present and some not."""
        item = MagicMock()
        item.files = [
            {"name": "present.txt"},
            {"name": "gone_a.txt"},
            {"name": "gone_b.txt"},
        ]

        item_dir = tmp_path / "partial"
        item_dir.mkdir()
        (item_dir / "present.txt").write_text("ok")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("partial", str(tmp_path))

        assert result.complete is False
        assert result.files_expected == 3
        assert result.files_found == 1
        assert set(result.files_missing) == {
            "gone_a.txt",
            "gone_b.txt",
        }

    def test_all_files_missing(self, tmp_path):
        """Item directory exists but contains none of the files."""
        item = MagicMock()
        item.files = [
            {"name": "a.txt"},
            {"name": "b.txt"},
        ]

        item_dir = tmp_path / "empty-dir"
        item_dir.mkdir()

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("empty-dir", str(tmp_path))

        assert result.complete is False
        assert result.files_expected == 2
        assert result.files_found == 0
        assert len(result.files_missing) == 2


# ---------------------------------------------------------
# No item directory on disk
# ---------------------------------------------------------


class TestVerifyNoItemDir:
    """The item directory does not exist at all."""

    def test_no_item_dir(self, tmp_path):
        """Item dir missing means all files are missing."""
        item = MagicMock()
        item.files = [{"name": "file.txt"}]

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("nonexistent", str(tmp_path))

        assert result.complete is False
        assert result.files_expected == 1
        assert result.files_found == 0
        assert result.files_missing == ["file.txt"]

    def test_no_item_dir_multiple_files(self, tmp_path):
        """Multiple files expected but no item dir at all."""
        item = MagicMock()
        item.files = [
            {"name": "alpha.txt"},
            {"name": "beta.txt"},
            {"name": "gamma.txt"},
        ]

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify(
            "nowhere", str(tmp_path)
        )

        assert result.complete is False
        assert result.files_expected == 3
        assert result.files_found == 0
        assert len(result.files_missing) == 3


# ---------------------------------------------------------
# Empty item (no files in metadata)
# ---------------------------------------------------------


class TestVerifyEmptyItem:
    """The item has no files in its metadata."""

    def test_empty_files_list(self, tmp_path):
        """item.files is an empty list => complete."""
        item = MagicMock()
        item.files = []

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("empty-item", str(tmp_path))

        assert result.complete is True
        assert result.files_expected == 0
        assert result.files_found == 0
        assert result.files_missing == []

    def test_none_files_list(self, tmp_path):
        """item.files is None => treated as empty."""
        item = MagicMock()
        item.files = None

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("none-item", str(tmp_path))

        assert result.complete is True
        assert result.files_expected == 0
        assert result.files_found == 0
        assert result.files_missing == []


# ---------------------------------------------------------
# Error handling
# ---------------------------------------------------------


class TestVerifyErrorHandling:
    """Edge cases and error conditions."""

    def test_get_item_exception_returns_incomplete(
        self, tmp_path
    ):
        """If session.get_item() raises, verify returns an
        incomplete result rather than propagating."""
        def bad_factory():
            session = MagicMock()
            session.get_item.side_effect = Exception(
                "network error"
            )
            return session

        worker = DownloadWorker(
            session_factory=bad_factory,
            download_kwargs={},
        )
        result = worker.verify("broken", str(tmp_path))

        assert isinstance(result, VerifyResult)
        assert result.complete is False
        assert result.files_expected == 0
        assert result.files_found == 0
        assert result.files_missing == []
        assert result.identifier == "broken"

    def test_files_missing_name_key_skipped(self, tmp_path):
        """File entries without a 'name' key are ignored."""
        item = MagicMock()
        item.files = [
            {"name": "good.txt"},
            {"source": "metadata"},  # no "name" key
        ]

        item_dir = tmp_path / "skip-item"
        item_dir.mkdir()
        (item_dir / "good.txt").write_text("ok")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify("skip-item", str(tmp_path))

        assert result.complete is True
        assert result.files_expected == 1
        assert result.files_found == 1
        assert result.files_missing == []


# ---------------------------------------------------------
# Subdirectory files
# ---------------------------------------------------------


class TestVerifySubdirectoryFiles:
    """Files with path separators in their names."""

    def test_nested_file_present(self, tmp_path):
        """A file in a subdirectory is found correctly."""
        item = MagicMock()
        item.files = [
            {"name": "subdir/nested.txt"},
        ]

        item_dir = tmp_path / "nested-item"
        item_dir.mkdir()
        sub = item_dir / "subdir"
        sub.mkdir()
        (sub / "nested.txt").write_text("deep")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify(
            "nested-item", str(tmp_path)
        )

        assert result.complete is True
        assert result.files_found == 1

    def test_nested_file_missing(self, tmp_path):
        """A file in a subdirectory that is missing."""
        item = MagicMock()
        item.files = [
            {"name": "subdir/missing.txt"},
        ]

        item_dir = tmp_path / "nested-item"
        item_dir.mkdir()

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify(
            "nested-item", str(tmp_path)
        )

        assert result.complete is False
        assert result.files_missing == [
            "subdir/missing.txt"
        ]


# ---------------------------------------------------------
# Result fields
# ---------------------------------------------------------


class TestVerifyResultFields:
    """Verify that VerifyResult fields are populated
    correctly."""

    def test_identifier_field_set(self, tmp_path):
        """The identifier field matches what was requested."""
        item = MagicMock()
        item.files = []

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify(
            "my-identifier", str(tmp_path)
        )

        assert result.identifier == "my-identifier"

    def test_files_corrupted_defaults_empty(self, tmp_path):
        """The files_corrupted field defaults to an empty
        list (verify does not check checksums)."""
        item = MagicMock()
        item.files = [{"name": "x.txt"}]

        item_dir = tmp_path / "corrupt-check"
        item_dir.mkdir()
        (item_dir / "x.txt").write_text("data")

        worker = DownloadWorker(
            session_factory=_mock_session_factory(item),
            download_kwargs={},
        )
        result = worker.verify(
            "corrupt-check", str(tmp_path)
        )

        assert result.files_corrupted == []
