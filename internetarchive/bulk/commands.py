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
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
internetarchive.bulk.commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CLI-facing entry points for bulk operations.

Bridges the ``ia download`` CLI arguments with the bulk engine,
worker, disk pool, job log, and UI components.

:copyright: (C) 2012-2024 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time

from internetarchive.bulk.disk import DiskPool, parse_size
from internetarchive.bulk.engine import BulkEngine
from internetarchive.bulk.jobs import JobLog
from internetarchive.bulk.ui.plain import PlainUI, _format_bytes
from internetarchive.workers.download import DownloadWorker


def _get_identifiers(
    args: argparse.Namespace,
) -> tuple[list[str], int | None]:
    """Build an identifier list from CLI args.

    Reads from ``--itemlist``, ``--search``, or stdin
    (``identifier == "-"``).

    Returns:
        A tuple of (identifier_list, total_count).
        *total_count* is ``None`` when reading from stdin
        and the total is unknown.
    """
    if args.itemlist:
        ids = [
            line.strip()
            for line in args.itemlist
            if line.strip()
        ]
        return ids, len(ids)

    if args.search:
        _search = args.session.search_items(
            args.search,
            params=getattr(args, "search_parameters", None),
        )
        total = _search.num_found
        if total == 0:
            print(
                f"error: the query '{args.search}' "
                "returned no results",
                file=sys.stderr,
            )
            sys.exit(1)
        ids = [r["identifier"] for r in _search]
        return ids, len(ids)

    # stdin mode (identifier == "-")
    ids = [
        line.strip()
        for line in sys.stdin
        if line.strip()
    ]
    return ids, len(ids)


def _build_download_kwargs(
    args: argparse.Namespace,
) -> dict:
    """Map CLI args to ``Item.download()`` keyword arguments.

    Returns:
        A dict suitable for passing to
        :class:`~internetarchive.workers.download.DownloadWorker`.
    """
    kwargs: dict = {}

    if getattr(args, "glob", None):
        kwargs["glob_pattern"] = args.glob
    if getattr(args, "exclude", None):
        kwargs["exclude_pattern"] = args.exclude
    if getattr(args, "format", None):
        kwargs["formats"] = args.format
    if getattr(args, "source", None):
        kwargs["source"] = args.source
    if getattr(args, "exclude_source", None):
        kwargs["exclude_source"] = args.exclude_source

    kwargs["dry_run"] = getattr(args, "dry_run", False)
    kwargs["verbose"] = not getattr(args, "quiet", False)
    kwargs["ignore_existing"] = getattr(args, "ignore_existing", False)
    kwargs["checksum"] = getattr(args, "checksum", False)
    kwargs["checksum_archive"] = getattr(args, "checksum_archive", False)
    kwargs["no_directory"] = getattr(args, "no_directories", False)
    kwargs["retries"] = getattr(args, "retries", 5)
    kwargs["on_the_fly"] = getattr(args, "on_the_fly", False)
    kwargs["no_change_timestamp"] = getattr(args, "no_change_timestamp", False)
    kwargs["ignore_history_dir"] = not getattr(args, "download_history", False)
    kwargs["stdout"] = getattr(args, "stdout", False)

    params = getattr(args, "parameters", None)
    if params:
        kwargs["params"] = params

    timeout = getattr(args, "timeout", None)
    if timeout is not None:
        kwargs["timeout"] = timeout

    return kwargs


def _make_session_factory(args: argparse.Namespace):
    """Return a callable that creates per-thread ArchiveSessions."""
    config_file = getattr(args, "config_file", None)

    def factory():
        from internetarchive import get_session  # noqa: PLC0415
        return get_session(config_file=config_file)

    return factory


def _select_ui(args, num_workers, total_count):
    """Select the appropriate UI backend.

    Resolution order:
    - ``--no-ui`` → :class:`PlainUI`
    - ``--ui`` or stderr is a TTY → try :class:`RichTUI`
      → try :class:`CursesTUI` → fall back to :class:`PlainUI`
    - Otherwise → :class:`PlainUI`
    """
    if getattr(args, "no_ui", False):
        return PlainUI(
            total_items=total_count, num_workers=num_workers,
        )

    use_tui = getattr(args, "ui", False) or sys.stderr.isatty()

    if use_tui:
        try:
            from internetarchive.bulk.ui.rich_tui import (  # noqa: PLC0415
                HAS_RICH,
                RichTUI,
            )
            if HAS_RICH:
                return RichTUI(
                    num_workers=num_workers,
                    total_items=total_count,
                )
        except ImportError:  # pragma: no cover
            pass

        try:
            from internetarchive.bulk.ui.tui import (  # noqa: PLC0415
                CursesTUI,
            )
            return CursesTUI(
                num_workers=num_workers,
                total_items=total_count,
            )
        except ImportError:  # pragma: no cover
            pass

    return PlainUI(
        total_items=total_count, num_workers=num_workers,
    )


def bulk_download(args: argparse.Namespace) -> None:
    """Entry point for bulk download mode.

    Activated when ``--workers > 1`` with a multi-item input
    source (``--itemlist``, ``--search``, or stdin).

    Builds and runs a
    :class:`~internetarchive.bulk.engine.BulkEngine` with a
    :class:`~internetarchive.workers.download.DownloadWorker`.
    """
    ids, total_count = _get_identifiers(args)
    if not ids:
        print("error: no identifiers provided", file=sys.stderr)
        sys.exit(1)

    # Destination directories.
    destdirs = getattr(args, "destdirs", None)
    if not destdirs:
        destdir = getattr(args, "destdir", None) or "."
        destdirs = [destdir]

    # Disk margin.
    margin_str = getattr(args, "disk_margin", "1G")
    margin = parse_size(margin_str)
    no_disk_check = getattr(args, "no_disk_check", False)

    disk_pool = DiskPool(
        destdirs=destdirs,
        margin=margin,
        disabled=no_disk_check,
    )

    # Job log.
    joblog_path = getattr(args, "joblog", None)
    if joblog_path:
        job_log = JobLog(joblog_path)
    else:
        job_log = JobLog(_null_joblog_path())

    # Download kwargs.
    download_kwargs = _build_download_kwargs(args)

    # UI.
    num_workers = getattr(args, "workers", 1)
    ui = _select_ui(args, num_workers, total_count)

    has_lifecycle = hasattr(ui, "start")

    # Suppress Item.download() verbose output when a TUI is
    # active — the TUI displays progress via its own events.
    if has_lifecycle:
        download_kwargs["verbose"] = False

    worker = DownloadWorker(
        session_factory=_make_session_factory(args),
        download_kwargs=download_kwargs,
    )
    if has_lifecycle:
        ui.start()

    engine = BulkEngine(
        worker=worker,
        job_log=job_log,
        disk_pool=disk_pool,
        num_workers=num_workers,
        ui_handler=ui.handle_event,
    )

    t0 = time.time()
    try:
        result = engine.run(ids)
    finally:
        if has_lifecycle:
            ui.stop()

    elapsed = time.time() - t0

    # Get total bytes from job log status.
    status = job_log.status()
    total_bytes = status.get("total_bytes", 0)

    if hasattr(ui, "print_summary"):
        ui.print_summary(
            completed=result["completed"],
            failed=result["failed"],
            skipped=result["skipped"],
            total_bytes=total_bytes,
            elapsed=elapsed,
        )
    else:
        summary = (
            f"Summary: {result['completed']} completed, "
            f"{result['failed']} failed, "
            f"{result['skipped']} skipped, "
            f"{_format_bytes(total_bytes)} "
            f"in {elapsed:.1f}s"
        )
        print(summary, file=sys.stderr)

    job_log.close()

    if result["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


def bulk_status(joblog_path: str) -> None:
    """Print a summary of a job log and exit.

    Used with ``ia download --status --joblog <path>``.
    """
    try:
        job_log = JobLog(joblog_path)
    except FileNotFoundError:
        print(
            f"error: job log not found: {joblog_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    status = job_log.status()
    job_log.close()

    print(f"completed: {status['completed']}")
    print(f"failed:    {status['failed']}")
    print(f"skipped:   {status['skipped']}")
    total_bytes = status.get("total_bytes", 0)
    print(f"bytes:     {total_bytes}")

    failed_items = status.get("failed_items", [])
    if failed_items:
        print("\nFailed items:")
        for ident, error in failed_items:
            print(f"  {ident}: {error}")


def bulk_verify(args: argparse.Namespace) -> None:
    """Verify on-disk completeness of downloaded items.

    Reads the job log to find completed items, then uses
    :meth:`DownloadWorker.verify` to check each one.
    """
    joblog_path = getattr(args, "joblog", None)
    if not joblog_path:
        print(
            "error: --verify requires --joblog",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        job_log = JobLog(joblog_path)
    except FileNotFoundError:
        print(
            f"error: job log not found: {joblog_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    status = job_log.status()

    if status["completed"] == 0:
        job_log.close()
        print("No completed items to verify.")
        return

    download_kwargs = _build_download_kwargs(args)
    worker = DownloadWorker(
        session_factory=_make_session_factory(args),
        download_kwargs=download_kwargs,
    )

    destdir = getattr(args, "destdir", None) or "."

    ok_count = 0
    bad_count = 0

    # Access internal state to find completed identifiers.
    items = job_log._items  # noqa: SLF001
    for ident, (event, _detail) in items.items():
        if event != "completed":
            continue
        result = worker.verify(ident, destdir)
        if result.complete:
            ok_count += 1
        else:
            bad_count += 1
            missing = ", ".join(result.files_missing[:5])
            print(
                f"{ident}: INCOMPLETE "
                f"({result.files_found}/{result.files_expected})"
                f" missing: {missing}"
            )

    job_log.close()

    print(
        f"\nVerification: {ok_count} OK, "
        f"{bad_count} incomplete"
    )

    if bad_count > 0:
        sys.exit(1)


def _null_joblog_path() -> str:
    """Return a path for a temporary job log.

    Uses a temp file in the system temp directory so that
    bulk operations without ``--joblog`` still have a
    functioning :class:`JobLog` instance.
    """
    fd, path = tempfile.mkstemp(prefix="ia_bulk_", suffix=".jsonl")
    os.close(fd)
    return path
