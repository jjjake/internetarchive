"""
internetarchive.workers.download
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Download worker for the bulk operations engine.

Wraps ``Item.download()`` with DiskPool integration, per-thread
session management, and cancel event support.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable

from internetarchive.bulk.ui import UIEvent
from internetarchive.bulk.worker import BaseWorker, WorkerResult
from internetarchive.exceptions import DownloadCancelled

if TYPE_CHECKING:
    from threading import Event

    from internetarchive.bulk.disk import DiskPool
    from internetarchive.session import ArchiveSession


class DownloadWorker(BaseWorker):
    """Worker that downloads an Archive.org item.

    :param session: An ``ArchiveSession`` used to create per-thread
        sessions and retrieve items.
    :param disk_pool: Optional ``DiskPool`` for multi-disk routing.
        If ``None``, downloads go to the first ``destdir`` or cwd.
    :param destdir: Default destination directory (used when
        ``disk_pool`` is ``None``).
    :param progress_emitter: Optional callable that accepts a
        ``UIEvent`` and forwards it to the UI handler. Set by the
        engine to enable per-file progress reporting.
    :param download_kwargs: Extra keyword arguments passed through
        to ``Item.download()`` (e.g. ``glob_pattern``, ``checksum``,
        ``format``, ``retries``).
    """

    def __init__(
        self,
        session: ArchiveSession,
        disk_pool: DiskPool | None = None,
        destdir: str | None = None,
        progress_emitter: (
            Callable[[UIEvent], None] | None
        ) = None,
        **download_kwargs,
    ):
        self._session = session
        self._disk_pool = disk_pool
        self._destdir = destdir
        self._progress_emitter = progress_emitter
        self._download_kwargs = download_kwargs
        self._local = threading.local()

    def _get_session(self) -> ArchiveSession:
        """Get or create a per-thread session.

        :returns: An ``ArchiveSession`` instance for the current
            thread.
        """
        if not hasattr(self._local, "session"):
            from internetarchive import get_session  # noqa: PLC0415
            self._local.session = get_session(
                config=self._session.config,
                config_file=self._session.config_file,
            )
        return self._local.session

    def execute(  # noqa: PLR0911
        self,
        job: dict,
        cancel_event: Event,
    ) -> WorkerResult:
        """Download an item.

        :param job: Job dict from the joblog. Uses ``job["id"]``
            as the Archive.org item identifier.
        :param cancel_event: Event set on graceful shutdown.
        :returns: ``WorkerResult`` with download outcome.
        """
        identifier = job.get("id", "")
        if cancel_event.is_set():
            return WorkerResult(
                success=False,
                identifier=identifier,
                error="cancelled",
                retry=False,
            )

        session = self._get_session()

        # Fetch item metadata first so we know the size for
        # disk pool reservation.
        try:
            item = session.get_item(identifier)
        except Exception as exc:
            error_msg = str(exc)
            is_permanent = (
                "dark" in error_msg.lower()
                or "does not exist" in error_msg.lower()
            )
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=error_msg,
                retry=not is_permanent,
            )

        if item.is_dark:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error="item is dark",
                retry=False,
            )

        if item.metadata == {}:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error="item does not exist",
                retry=False,
            )

        # Route to a disk with enough space for this item.
        destdir = self._destdir
        estimated_bytes = item.item_size or 0
        routed_path = None

        if self._disk_pool is not None:
            routed_path = self._disk_pool.route(estimated_bytes)
            if routed_path is None:
                return WorkerResult(
                    success=False,
                    identifier=identifier,
                    error="all disks full",
                    backoff=True,
                )
            destdir = routed_path

        # Build progress closures when the emitter is wired.
        progress_cb = None
        file_cb = None
        if self._progress_emitter is not None:
            worker_idx = job.get("_worker_idx", 0)
            emitter = self._progress_emitter

            def _on_chunk(bytes_written):
                emitter(UIEvent(
                    kind="file_progress",
                    identifier=identifier,
                    worker=worker_idx,
                    extra={"bytes": bytes_written},
                ))

            def _on_file(action, name, size, idx, count):
                kind = (
                    "file_started"
                    if action == "start"
                    else "file_completed"
                )
                emitter(UIEvent(
                    kind=kind,
                    identifier=identifier,
                    worker=worker_idx,
                    extra={
                        "file_name": name,
                        "file_size": size or 0,
                        "file_index": idx,
                        "file_count": count,
                    },
                ))

            progress_cb = _on_chunk
            file_cb = _on_file

        try:
            errors = item.download(
                destdir=destdir,
                verbose=False,
                ignore_errors=True,
                cancel_event=cancel_event,
                progress_callback=progress_cb,
                file_callback=file_cb,
                **self._download_kwargs,
            )
        except DownloadCancelled:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error="cancelled",
                retry=False,
            )
        except Exception as exc:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=str(exc),
                retry=True,
            )
        finally:
            if self._disk_pool and routed_path:
                self._disk_pool.release(
                    routed_path, estimated_bytes
                )

        if errors:
            return WorkerResult(
                success=False,
                identifier=identifier,
                error=f"{len(errors)} file(s) failed",
                retry=True,
                extra={"failed_files": errors},
            )

        return WorkerResult(
            success=True,
            identifier=identifier,
            extra={"item_size": estimated_bytes},
        )
