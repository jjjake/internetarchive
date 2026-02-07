.. _bulk-download:

Bulk Downloading
================

The ``ia download`` command includes a built-in bulk download engine
for downloading many items concurrently. This replaces the need for
external tools like GNU Parallel for most bulk download use cases.

The bulk download engine provides:

- **Concurrent downloads** -- download multiple items in parallel
  using a configurable number of worker threads
- **Resume support** -- a JSONL job log tracks progress so that
  interrupted downloads automatically skip completed items on re-run
- **Multi-disk routing** -- spread downloads across multiple
  destination directories with automatic disk space monitoring
- **Status and verification** -- inspect job progress and verify
  on-disk completeness without re-downloading

Bulk mode is activated when ``--workers`` is greater than 1 and a
multi-item source is provided (``--search``, ``--itemlist``, or
stdin).

.. contents:: On This Page
   :local:
   :depth: 2


Quick Start
-----------

Download items from a search query with 4 concurrent workers:

.. code:: bash

    $ ia download --search 'collection:nasa' \
        --workers 4 --joblog nasa.jsonl

Download items from a plain-text item list with 8 workers:

.. code:: bash

    $ ia download --itemlist items.txt \
        -w 8 --joblog batch.jsonl

If the download is interrupted, simply re-run the same command.
Completed items are automatically skipped:

.. code:: bash

    $ ia download --itemlist items.txt \
        -w 8 --joblog batch.jsonl


CLI Options
-----------

The following options control bulk download behavior. They can be
combined with all existing ``ia download`` options (``--glob``,
``--format``, ``--checksum``, etc.).

``--workers N``, ``-w N``
    Number of concurrent item download workers (default: 1).
    Values greater than 1 activate the bulk download engine.
    Each worker operates on a separate item in its own thread
    with its own HTTP session.

``--joblog PATH``
    Path to a JSONL job log file. The engine appends one line
    per event (started, completed, failed, skipped) so progress
    is recorded incrementally. On re-run, the engine reads this
    file to determine which items have already been completed
    and skips them automatically.

``--destdirs DIR [DIR ...]``
    One or more destination directories. Items are routed to
    the first directory with sufficient free space. This is
    useful when downloading large collections that span
    multiple disks.

``--disk-margin SIZE``
    Minimum free space to maintain on each disk (default:
    ``1G``). Accepts human-readable suffixes: ``K``, ``M``,
    ``G``, ``T`` (e.g. ``500M``, ``2G``, ``1T``). Items
    will not be routed to a disk with less than this amount
    of free space.

``--no-disk-check``
    Disable automatic disk space checking entirely. Items
    are always routed to the first destination directory.

``--status``
    Print a summary of the job log and exit. Requires
    ``--joblog``. Does not download anything.

``--verify``
    Verify that all completed items are fully present on
    disk and exit. Requires ``--joblog``. Reports any
    items with missing files.


Item Sources
------------

The bulk download engine works with the same item sources as
regular ``ia download``:

**Search query** (``--search``)
    Downloads all items matching an Archive.org search query.

    .. code:: bash

        $ ia download --search 'collection:prelinger' \
            -w 4 --joblog prelinger.jsonl

**Item list file** (``--itemlist``)
    Downloads items listed in a plain text file (one identifier
    per line).

    .. code:: bash

        $ ia download --itemlist my_items.txt \
            -w 8 --joblog batch.jsonl

**Standard input** (``-``)
    Reads identifiers from stdin. This is useful for piping
    search results directly into the download engine.

    .. code:: bash

        $ ia search 'collection:books' --itemlist \
            | ia download - -w 4 --joblog books.jsonl


Job Log
-------

The job log is a JSONL (newline-delimited JSON) file where each
line records one event. The engine uses it for two purposes:

1. **Resume** -- on re-run, completed items are skipped
   automatically.
2. **Auditing** -- the log provides a record of what happened
   to each item.

Events recorded in the job log:

- ``started`` -- a worker began downloading the item
- ``completed`` -- the item downloaded successfully
- ``failed`` -- the item download encountered an error
- ``skipped`` -- the item was skipped (already completed,
  dark item, no disk space, etc.)

Example job log entries:

.. code:: json

    {"id":"nasa-photo-001","event":"started","op":"download","destdir":".","worker":"Thread-1","retry":0,"ts":"2026-01-15T10:30:00+00:00"}
    {"id":"nasa-photo-001","event":"completed","op":"download","destdir":".","bytes_transferred":52428800,"files_ok":12,"files_skipped":0,"files_failed":0,"elapsed":8.3,"ts":"2026-01-15T10:30:08+00:00"}

Checking Status
^^^^^^^^^^^^^^^

You can inspect the job log at any time (even while a download
is running in another terminal) using ``--status``:

.. code:: bash

    $ ia download --status --joblog nasa.jsonl
    completed: 142
    failed:    3
    skipped:   5
    bytes:     10737418240

    Failed items:
      nasa-photo-099: connection timeout
      nasa-photo-203: 503 Service Unavailable
      nasa-photo-417: item nasa-photo-417 is dark

Resume Semantics
^^^^^^^^^^^^^^^^

The resume logic follows these rules:

- **completed** items are always skipped
- **failed** items are retried
- **skipped** items with reason ``no_disk_space`` are retried
- **skipped** items with reason ``exists``, ``dark``, or
  ``empty`` are not retried
- Items that were ``started`` but never completed (e.g. due
  to a crash) are retried


Multi-Disk Downloads
--------------------

When downloading large collections that may not fit on a single
disk, use ``--destdirs`` to provide multiple destination
directories:

.. code:: bash

    $ ia download --search 'collection:large_dataset' \
        -w 4 \
        --destdirs /mnt/disk1 /mnt/disk2 /mnt/disk3 \
        --joblog large.jsonl \
        --disk-margin 2G

The engine routes each item to the first directory in the list
that has sufficient free space (accounting for the safety margin
and any space reserved by concurrent workers). If an item's
estimated size exceeds the available space on all disks, it is
skipped with a ``no_disk_space`` reason in the job log.

The ``--disk-margin`` value (default ``1G``) is the minimum
free space the engine will leave on each disk. This prevents
the filesystem from filling up completely.

To disable disk space checking (for example, if you know you
have enough space or are using a network filesystem where
``statvfs`` is unreliable), use ``--no-disk-check``:

.. code:: bash

    $ ia download --search 'collection:example' \
        -w 4 --no-disk-check --joblog example.jsonl


Verifying Downloads
-------------------

After a bulk download completes, you can verify that all items
are fully present on disk:

.. code:: bash

    $ ia download --verify \
        --itemlist items.txt --joblog batch.jsonl

The verify command checks each completed item in the job log
against the item's file list from Archive.org metadata. It
reports any items with missing files:

.. code:: text

    nasa-photo-099: INCOMPLETE (10/12) missing: thumb.jpg, meta.xml

    Verification: 139 OK, 1 incomplete

If any items are incomplete, the command exits with a non-zero
status code.


Combining with Other Download Options
--------------------------------------

All standard ``ia download`` options work in bulk mode. For
example, to download only MP4 files from a collection:

.. code:: bash

    $ ia download --search 'collection:movies' \
        -w 4 --glob '*.mp4' --joblog movies.jsonl

Or to download only original files with checksum verification:

.. code:: bash

    $ ia download --itemlist items.txt \
        -w 8 --source original --checksum \
        --joblog originals.jsonl


Comparison with GNU Parallel
-----------------------------

Previous versions of this documentation recommended using
`GNU Parallel <https://www.gnu.org/software/parallel/>`_
for concurrent downloads (see :ref:`parallel`). The built-in
bulk download engine offers several advantages:

- **No external dependency** -- no need to install GNU Parallel
- **Integrated resume** -- the JSONL job log provides
  automatic resume without manual ``--joblog`` + ``--retry``
  management
- **Disk-aware routing** -- automatic space monitoring and
  multi-disk support
- **Per-item progress** -- the engine emits per-item events
  for status tracking

GNU Parallel remains useful for other ``ia`` operations (such
as concurrent metadata writes) and for users who prefer its
flexibility. See :ref:`parallel` for details.


Troubleshooting
---------------

**Download hangs or is very slow**
    Try reducing the number of workers. Archive.org may
    rate-limit connections from a single IP.

**"no_disk_space" skips even though disk has space**
    The engine reserves space for all in-flight downloads
    concurrently. With many workers and large items, the
    reserved space can exceed actual usage. Try increasing
    ``--disk-margin`` headroom, or use ``--no-disk-check``
    if you are confident in available space.

**"item is dark" errors**
    Dark items are not publicly accessible. These are
    skipped automatically and recorded in the job log.

**Job log grows very large**
    The job log is append-only. For very large jobs
    (hundreds of thousands of items), the file may grow
    significantly. The engine reads it only once at
    startup, so this does not affect runtime performance.
