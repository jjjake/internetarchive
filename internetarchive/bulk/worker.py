"""
internetarchive.bulk.worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Base worker interface for bulk operations.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Event


@dataclass
class WorkerResult:
    """Result returned by a worker after processing a job.

    :param success: Whether the job completed successfully.
    :param identifier: The Archive.org identifier that was processed.
    :param error: Error message if the job failed.
    :param backoff: Signal the engine to pause new submissions
        (e.g. disk full, rate limited).
    :param retry: Whether the engine should retry on failure.
        Set to ``False`` for permanent failures (dark item, 404).
    :param extra: Opaque dict written to the joblog event line.
    """

    success: bool
    identifier: str
    error: str | None = None
    backoff: bool = False
    retry: bool = True
    extra: dict | None = field(default_factory=dict)


class BaseWorker(ABC):
    """Abstract base class for bulk operation workers.

    Workers implement ``execute()`` to perform a single job.
    The engine calls this method from a thread pool and records
    the result in the joblog.
    """

    @abstractmethod
    def execute(
        self,
        job: dict,
        cancel_event: Event,
    ) -> WorkerResult:
        """Execute a single job.

        :param job: The full job dict from the joblog. Workers
            extract whatever fields they need (e.g. ``job["id"]``
            for identifier-based operations). The engine passes
            the dict through opaquely.
        :param cancel_event: Threading event set when the engine
            wants to shut down gracefully. Workers should check
            this periodically and return early if set.
        :returns: A ``WorkerResult`` describing the outcome.
        """
        ...
