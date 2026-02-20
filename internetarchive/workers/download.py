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

        Per-thread sessions use HTTP keep-alive and larger
        connection pools to avoid the overhead of repeated
        TCP+TLS handshakes across files within the same item.

        :returns: An ``ArchiveSession`` instance for the current
            thread.
        """
        if not hasattr(self._local, "session"):
            from internetarchive import get_session  # noqa: PLC0415
            session = get_session(
                config=self._session.config,
                config_file=self._session.config_file,
            )
            # Enable HTTP keep-alive for bulk downloads.
            # The default Connection: close header forces a
            # new TCP+TLS handshake per request — wasteful
            # when downloading many files from the same host.
            session.headers.pop("Connection", None)
            # Mount a pooled adapter on archive.org (for
            # metadata/redirect requests).
            session.mount_http_adapter(
                pool_connections=10,
                pool_maxsize=10,
            )
            # Downloads 302-redirect to ia*.us.archive.org,
            # so replace the default https:// adapter with
            # one that has a larger connection pool.
            from requests.adapters import HTTPAdapter  # noqa: PLC0415
            session.mount(
                "https://",
                HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=10,
                ),
            )
            # CRITICAL: File.download() calls
            # session.mount_http_adapter() on EVERY file,
            # which creates a new HTTPAdapter and destroys
            # the connection pool.  Prevent that.
            session.mount_http_adapter = (  # type: ignore[method-assign]
                lambda **kw: None
            )
            self._local.session = session
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

        # Hoist worker_idx so it's available for both the
        # routing event and the file-progress closures below.
        worker_idx = job.get("_worker_idx", 0)

        if self._progress_emitter is not None:
            self._progress_emitter(UIEvent(
                kind="job_routed",
                identifier=identifier,
                worker=worker_idx,
                extra={"destdir": destdir or "."},
            ))

        # Build progress closures when the emitter is wired.
        progress_cb = None
        file_cb = None
        if self._progress_emitter is not None:
            emitter = self._progress_emitter
            # Buffer progress bytes and only emit every
            # _REPORT_INTERVAL to avoid overwhelming the
            # UI handler.  iter_content yields small TLS
            # record-sized chunks (~16 KB), NOT full
            # chunk_size reads — without throttling, 8
            # workers generate ~768 callbacks/second.
            _REPORT_INTERVAL = 2 * 1024 * 1024
            _buf = [0]

            def _flush_buf():
                if _buf[0] > 0:
                    emitter(UIEvent(
                        kind="file_progress",
                        identifier=identifier,
                        worker=worker_idx,
                        extra={"bytes": _buf[0]},
                    ))
                    _buf[0] = 0

            def _on_chunk(bytes_written):
                _buf[0] += bytes_written
                if _buf[0] >= _REPORT_INTERVAL:
                    _flush_buf()

            def _on_file(action, name, size, idx, count):
                if action != "start":
                    _flush_buf()
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
