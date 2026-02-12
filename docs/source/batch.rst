.. _batch:

Batch Operations
================

.. versionadded:: 5.8

The ``ia`` CLI includes a built-in batch engine for processing many
items concurrently. It provides job logging with automatic resume,
multi-disk routing, graceful shutdown, and configurable workers —
no extra tools required.

Batch mode currently supports **downloads**, with support for
uploads and metadata operations planned for future releases.


Quick Start
-----------

Download items from a search query with four concurrent workers:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl \
        download --search 'collection:prelinger'

Download items from a file of identifiers:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl \
        download --itemlist items.txt

Resume an interrupted session (no identifier or search needed):

.. code:: console

    $ ia --workers 4 --joblog session.jsonl download


Job Logging and Resume
----------------------

The ``--joblog`` flag writes an append-only JSONL log that tracks
every job and its outcome. Each line records an event (``job``,
``started``, ``completed``, or ``failed``) with a timestamp and
sequence number.

To resume an interrupted session, re-run with the same ``--joblog``
path. The engine scans the log, builds a bitmap of completed jobs,
and processes only the remaining items:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl download

Check the status of a job log without running anything:

.. code:: console

    $ ia --joblog session.jsonl --status
    Job log: session.jsonl
      Total:     10000
      Completed: 3500
      Failed:    50
      Pending:   6450

.. note::

    ``--joblog`` is required when ``--workers`` is greater than 1.
    When using a single worker, ``--joblog`` is optional but still
    useful for resume support.


Multi-Disk Routing
------------------

Spread downloads across multiple disks by repeating ``--destdir``:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl \
        download --search 'collection:prelinger' \
        --destdir /mnt/disk1 --destdir /mnt/disk2

The engine routes each item to the disk with the most free space.
A configurable margin (default 1 GB) is reserved on each disk to
prevent filling it completely:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl \
        download --itemlist items.txt \
        --destdir /mnt/disk1 --destdir /mnt/disk2 \
        --disk-margin 500M

The ``--disk-margin`` flag accepts suffixes: ``K``, ``M``, ``G``,
``T``, or a plain number in bytes.

If all disks are full, the engine pauses for 30 seconds before
retrying. To disable disk space checking entirely:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl \
        download --itemlist items.txt \
        --destdir /mnt/disk1 --no-disk-check


Graceful Shutdown
-----------------

Pressing **Ctrl+C** once initiates a graceful shutdown: in-progress
jobs finish, and all results are recorded in the job log.
Pressing **Ctrl+C** a second time exits immediately.

After a graceful shutdown, resume with the same ``--joblog`` path
to pick up where you left off.


Tuning Workers
--------------

The ``--workers`` flag controls how many items are processed
concurrently. The maximum is 20.

.. code:: console

    $ ia --workers 8 --joblog session.jsonl \
        download --search 'collection:prelinger'

Start with 4 workers and increase if your network and disk I/O can
handle more. Each worker creates its own HTTP session.

The ``--batch-retries`` flag sets how many times a failed job is
retried before being marked as permanently failed (default: 3).
This is separate from the per-file ``--retries`` flag (default: 5),
which controls HTTP-level retries within a single download:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl --batch-retries 5 \
        download --itemlist items.txt --retries 10


Filtering Files
---------------

All standard download filters work in batch mode:

.. code:: console

    $ ia --workers 4 --joblog session.jsonl \
        download --search 'collection:prelinger' --glob "*.mp4"

    $ ia --workers 4 --joblog session.jsonl \
        download --itemlist items.txt --format "512Kb MPEG4"

    $ ia --workers 4 --joblog session.jsonl \
        download --search 'collection:prelinger' --checksum

Supported filters: ``--glob``, ``--exclude``, ``--format``,
``--checksum``, ``--checksum-archive``, ``--on-the-fly``,
``--source``, ``--exclude-source``, ``--ignore-existing``,
``--no-directories``, and ``--no-change-timestamp``.


Unsupported Options
-------------------

The following download options are **not supported** in batch mode
and will produce an error if used:

- ``--dry-run`` — not compatible with the batch engine
- ``--stdout`` — not compatible with the batch engine
- Positional ``file`` arguments — use ``--glob`` to filter files
  within items instead


CLI Reference
-------------

**Global batch options** (appear before the subcommand in
``ia --help``):

``-w N, --workers N``
    Number of concurrent workers (default: 1). Setting this above 1
    enables batch mode.

``--joblog PATH``
    Path to a JSONL job log file. Required when ``--workers > 1``.
    Enables resume support.

``--batch-retries N``
    Number of times to retry a failed job (default: 3).

``--status``
    Print a summary of the job log and exit. Requires ``--joblog``.

**Download-specific batch options** (appear after ``download``):

``--destdir PATH``
    Destination directory. Repeatable for multi-disk routing.

``--disk-margin SIZE``
    Minimum free space to maintain on each disk (default: ``1G``).
    Accepts ``K``, ``M``, ``G``, ``T`` suffixes.

``--no-disk-check``
    Disable disk space checking entirely.


Python API
----------

The batch engine can also be used programmatically:

.. code:: python

    from internetarchive import get_session
    from internetarchive.bulk import BulkEngine, JobLog
    from internetarchive.bulk.disk import DiskPool
    from internetarchive.workers.download import DownloadWorker

    session = get_session()
    joblog = JobLog("session.jsonl")
    disk_pool = DiskPool(["/mnt/disk1", "/mnt/disk2"])
    worker = DownloadWorker(
        session,
        disk_pool=disk_pool,
        glob_pattern="*.pdf",
    )
    engine = BulkEngine(
        joblog=joblog,
        worker=worker,
        max_workers=4,
        retries=3,
    )

    # jobs is an iterable of (identifier, {}) tuples
    jobs = [("some-item-id", {}), ("another-item", {})]
    exit_code = engine.run(jobs, total=len(jobs), op="download")

Key classes:

- :class:`~internetarchive.bulk.engine.BulkEngine` — orchestrator
  that manages the thread pool, retries, and graceful shutdown
- :class:`~internetarchive.bulk.joblog.JobLog` — append-only JSONL
  log with resume bitmap
- :class:`~internetarchive.bulk.worker.BaseWorker` — abstract base
  for worker implementations
- :class:`~internetarchive.bulk.worker.WorkerResult` — result from
  a single job execution
- :class:`~internetarchive.bulk.disk.DiskPool` — multi-disk router
  with space reservation
- :class:`~internetarchive.workers.download.DownloadWorker` —
  downloads archive.org items
