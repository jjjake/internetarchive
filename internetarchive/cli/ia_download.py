"""
ia_download.py

'ia' subcommand for downloading files from archive.org.
"""

# Copyright (C) 2012-2026 Internet Archive
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

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from internetarchive.cli.cli_utils import (
    QueryStringAction,
    validate_dir_path,
)
from internetarchive.files import File
from internetarchive.search import Search


def setup(subparsers):
    """
    Setup args for download command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("download",
                                   aliases=["do"],
                                   help="Download files from archive.org",)

    # Main options
    parser.add_argument("identifier",
                        nargs="?",
                        type=str,
                        help="Identifier of the item to download")
    parser.add_argument("file",
                        nargs="*",
                        help="Files to download (only allowed with identifier)")

    # Additional options
    parser.add_argument("-q", "--quiet",
                        action="store_true",
                        help="Turn off ia's output")
    parser.add_argument("-d", "--dry-run",
                        action="store_true",
                        help="Print URLs to stdout and exit")
    parser.add_argument("-i", "--ignore-existing",
                        action="store_true",
                        help="Clobber files already downloaded")
    parser.add_argument("-C", "--checksum",
                        action="store_true",
                        help="Skip files based on checksum")
    parser.add_argument("--checksum-archive",
                        action="store_true",
                        help="Skip files based on _checksum_archive.txt file")
    parser.add_argument("-R", "--retries",
                        type=int,
                        default=5,
                        help="Set number of retries to <retries> (default: 5)")
    parser.add_argument("-I", "--itemlist",
                        type=argparse.FileType("r"),
                        help=("Download items from a specified file. "
                             "Itemlists should be a plain text file with one "
                             "identifier per line"))
    parser.add_argument("-S", "--search",
                        help="Download items returned from a specified search query")
    parser.add_argument("-P", "--search-parameters",
                        nargs=1,
                        action=QueryStringAction,
                        metavar="KEY:VALUE",
                        help="Parameters to send with your --search query. "
                             "Can be specified multiple times.")
    parser.add_argument("-g", "--glob",
                        help=("Only download files whose filename matches "
                             "the given glob pattern. You can provide multiple "
                             "patterns separated by a pipe symbol `|`"))
    parser.add_argument("-e", "--exclude",
                        help=("Exclude files whose filename matches "
                             "the given glob pattern. You can provide multiple "
                             "patterns separated by a pipe symbol `|`. You can only "
                             "use this option in conjunction with --glob"))
    parser.add_argument("-f", "--format",
                        nargs=1,
                        action="extend",
                        help=("Only download files of the specified format. "
                             "Can be specified multiple times. You can use the following "
                             "command to retrieve a list of file formats contained within "
                             "a given item: ia metadata --formats <identifier>"))
    parser.add_argument("--on-the-fly",
                        action="store_true",
                        help=("Download on-the-fly files, as well as other "
                             "matching files. on-the-fly files include derivative "
                             "EPUB, MOBI and DAISY files [default: False]"))
    parser.add_argument("--no-directories",
                        action="store_true",
                        help=("Download files into working directory. "
                             "Do not create item directories"))
    parser.add_argument("--destdir",
                        type=validate_dir_path,
                        nargs=1,
                        action="extend",
                        help=("The destination directory to download files "
                             "and item directories to. "
                             "Can be specified multiple times for "
                             "multi-disk routing in bulk mode"))
    parser.add_argument("-s", "--stdout",
                        action="store_true",
                        help="Write file contents to stdout")
    parser.add_argument("--no-change-timestamp",
                        action="store_true",
                        help=("Don't change the timestamp of downloaded files to reflect "
                             "the source material"))
    parser.add_argument("-p", "--parameters",
                        nargs=1,
                        action=QueryStringAction,
                        metavar="KEY:VALUE",
                        help="Parameters to send with your download request (e.g. `cnt=0`). "
                             "Can be specified multiple times.")
    parser.add_argument("-a", "--download-history",
                        action="store_true",
                        help="Also download files from the history directory")
    parser.add_argument("--source",
                        nargs=1,
                        action="extend",
                        help=("Filter files based on their source value in files.xml "
                             "(i.e. `original`, `derivative`, `metadata`). "
                             "Can be specified multiple times."))
    parser.add_argument("--exclude-source",
                        nargs=1,
                        action="extend",
                        help=("Exclude files based on their source value in files.xml "
                             "(i.e. `original`, `derivative`, `metadata`). "
                             "Can be specified multiple times."))
    parser.add_argument("-t", "--timeout",
                        type=float,
                        help=("Set a timeout for download requests. "
                             "This sets both connect and read timeout"))

    # Bulk mode options
    bulk_group = parser.add_argument_group(
        "bulk mode options",
        "Options for multi-disk routing (use with --workers)"
    )
    bulk_group.add_argument(
        "--disk-margin",
        type=str,
        default="1G",
        help=("Minimum free space to maintain on each disk "
              "(default: 1G). Supports K, M, G, T suffixes"))
    bulk_group.add_argument(
        "--no-disk-check",
        action="store_true",
        help="Disable disk space checking")

    parser.set_defaults(func=lambda args: main(args, parser))


def _parse_size(size_str: str) -> int:
    """Parse a human-readable size string to bytes.

    :param size_str: Size string like ``"1G"``, ``"500M"``, ``"2T"``.
    :returns: Size in bytes.
    :raises argparse.ArgumentTypeError: If the string is empty,
        negative, or not a valid size.
    """
    suffixes = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    size_str = size_str.strip().upper()
    if not size_str:
        raise argparse.ArgumentTypeError(
            "size cannot be empty"
        )
    try:
        if size_str[-1] in suffixes:
            value = float(size_str[:-1]) * suffixes[size_str[-1]]
        else:
            value = float(size_str)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid size: {size_str!r}"
        )
    if value < 0:
        raise argparse.ArgumentTypeError(
            f"size must be non-negative, got {size_str!r}"
        )
    return int(value)


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Validate download command arguments.

    :param args: Parsed arguments namespace.
    :param parser: Argument parser for error reporting.
    """
    # In bulk resume mode, identifier/search/itemlist not required
    if args.joblog and not args.identifier and not args.search and not args.itemlist:
        return

    if args.itemlist and args.search:
        parser.error("--itemlist and --search cannot be used together")

    if args.itemlist or args.search:
        if args.identifier:
            parser.error("Cannot specify an identifier with --itemlist/--search")
        if args.file:
            parser.error("Cannot specify files with --itemlist/--search")
    else:
        if not args.identifier:
            parser.error("Identifier is required when not using --itemlist/--search")


def _use_bulk_mode(args: argparse.Namespace) -> bool:
    """Determine whether to use the bulk engine.

    :param args: Parsed arguments namespace.
    :returns: ``True`` if bulk mode should be used.
    """
    return args.workers > 1 or bool(args.joblog)


def _run_bulk(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> None:
    """Run download in bulk mode using the BulkEngine.

    :param args: Parsed arguments namespace.
    :param parser: Argument parser for error reporting.
    """
    from internetarchive.bulk.disk import DiskPool  # noqa: PLC0415
    from internetarchive.bulk.engine import BulkEngine  # noqa: PLC0415
    from internetarchive.bulk.joblog import JobLog  # noqa: PLC0415
    from internetarchive.bulk.ui import (  # noqa: PLC0415
        NullUI,
        ProgressBarUI,
    )
    from internetarchive.workers.download import (  # noqa: PLC0415
        DownloadWorker,
    )

    if args.workers > 20:
        print(
            f"warning: capping workers at 20"
            f" (requested {args.workers})",
            file=sys.stderr,
        )
        args.workers = 20

    args.search_parameters = args.search_parameters or {}
    args.parameters = args.parameters or {}

    # Reject options that are not supported in bulk mode.
    if args.dry_run:
        parser.error(
            "--dry-run is not supported in bulk mode"
        )
    if args.stdout:
        parser.error(
            "--stdout is not supported in bulk mode"
        )
    if args.file:
        parser.error(
            "file arguments are not supported in bulk mode "
            "(use --glob to filter files)"
        )

    # Joblog path is required for bulk mode
    if not args.joblog:
        parser.error(
            "--joblog is required when using --workers > 1"
        )

    joblog = JobLog(args.joblog)

    # Single-pass scan for resume detection and progress state.
    snapshot = joblog.load()
    is_resume = snapshot["max_seq"] > 0

    # Build jobs iterator and total count
    jobs = None
    total = 0
    initial = 0

    if not is_resume:
        if args.search:
            _search = args.session.search_items(
                args.search, params=args.search_parameters
            )
            total = _search.num_found
            if total == 0:
                print(
                    f"error: the query '{args.search}' "
                    "returned no results",
                    file=sys.stderr,
                )
                sys.exit(1)
            jobs = _search
        elif args.itemlist:
            items = [
                x.strip() for x in args.itemlist if x.strip()
            ]
            if not items:
                parser.error(
                    "--itemlist file is empty or contains "
                    "only whitespace"
                )
            total = len(items)
            jobs = iter(
                [{"id": x} for x in items]
            )
        elif args.identifier:
            total = 1
            jobs = iter([{"id": args.identifier}])
        else:
            parser.error(
                "Identifier, --itemlist, or --search is required "
                "for initial bulk download"
            )
    else:
        status = snapshot["status"]
        total = status["total"]
        initial = status["completed"] + status["failed"]

    # Configure DiskPool
    destdirs = args.destdir or ["."]
    disk_pool = DiskPool(
        paths=destdirs,
        margin=_parse_size(args.disk_margin),
        check_space=not args.no_disk_check,
    )

    # Build download kwargs
    download_kwargs = {}
    if args.glob:
        download_kwargs["glob_pattern"] = args.glob
    if args.exclude:
        download_kwargs["exclude_pattern"] = args.exclude
    if args.format:
        download_kwargs["formats"] = args.format
    if args.checksum:
        download_kwargs["checksum"] = True
    if args.checksum_archive:
        download_kwargs["checksum_archive"] = True
    if args.ignore_existing:
        download_kwargs["ignore_existing"] = True
    if args.no_directories:
        download_kwargs["no_directory"] = True
    if args.on_the_fly:
        download_kwargs["on_the_fly"] = True
    if args.no_change_timestamp:
        download_kwargs["no_change_timestamp"] = True
    if args.parameters:
        download_kwargs["params"] = args.parameters
    if not args.download_history:
        download_kwargs["ignore_history_dir"] = True
    if args.source:
        download_kwargs["source"] = args.source
    if args.exclude_source:
        download_kwargs["exclude_source"] = args.exclude_source
    if args.timeout:
        download_kwargs["timeout"] = args.timeout
    if args.retries:
        download_kwargs["retries"] = args.retries

    worker = DownloadWorker(
        session=args.session,
        disk_pool=disk_pool,
        **download_kwargs,
    )

    engine = BulkEngine(
        joblog=joblog,
        worker=worker,
        max_workers=args.workers,
        retries=args.batch_retries,
        ui=NullUI() if args.quiet else ProgressBarUI(
            total=total, initial=initial,
            max_workers=args.workers,
        ),
    )

    rc = engine.run(jobs=jobs, total=total, op="download")
    sys.exit(rc)


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Main entry point for 'ia download'.

    :param args: Parsed arguments namespace.
    :param parser: Argument parser for error reporting.
    """
    # Dispatch to bulk mode if applicable
    if _use_bulk_mode(args):
        _run_bulk(args, parser)
        return

    args.search_parameters = args.search_parameters or {}
    args.parameters = args.parameters or {}

    # Normalize destdir: list → single value for single-item mode
    destdir = args.destdir[0] if args.destdir else None

    ids: list[File | str] | Search | TextIO
    validate_args(args, parser)

    if args.itemlist:
        ids = [x.strip() for x in args.itemlist if x.strip()]
        if not ids:
            parser.error("--itemlist file is empty or contains only whitespace")
        total_ids = len(ids)
    elif args.search:
        try:
            _search = args.session.search_items(args.search,
                                                params=args.search_parameters)
            total_ids = _search.num_found
            if total_ids == 0:
                print(f"error: the query '{args.search}' returned no results", file=sys.stderr)
                sys.exit(1)
            ids = _search
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(1)

    # Download specific files.
    if args.identifier and args.identifier != "-":
        if "/" in args.identifier:
            identifier = args.identifier.split("/")[0]
            files = ["/".join(args.identifier.split("/")[1:])]
        else:
            identifier = args.identifier
            files = args.file
        total_ids = 1
        ids = [identifier]
    elif args.identifier == "-":
        total_ids = 1
        ids = sys.stdin
        files = None
    else:
        files = None

    errors = []
    for i, identifier in enumerate(ids):
        try:
            identifier = identifier.strip()
        except AttributeError:
            identifier = identifier.get("identifier")
        if total_ids > 1:
            item_index = f"{i + 1}/{total_ids}"
        else:
            item_index = None

        try:
            item = args.session.get_item(identifier)
        except Exception as exc:
            print(f"{identifier}: failed to retrieve item metadata - errors", file=sys.stderr)
            if "You are attempting to make an HTTPS" in str(exc):
                print(f"\n{exc}", file=sys.stderr)
                sys.exit(1)
            else:
                continue

        # Otherwise, download the entire item.
        ignore_history_dir = not args.download_history
        _errors = item.download(
            files=files,
            formats=args.format,
            glob_pattern=args.glob,
            exclude_pattern=args.exclude,
            dry_run=args.dry_run,
            verbose=not args.quiet,
            ignore_existing=args.ignore_existing,
            checksum=args.checksum,
            checksum_archive=args.checksum_archive,
            destdir=destdir,
            no_directory=args.no_directories,
            retries=args.retries,
            item_index=item_index,
            ignore_errors=True,
            on_the_fly=args.on_the_fly,
            no_change_timestamp=args.no_change_timestamp,
            params=args.parameters,
            ignore_history_dir=ignore_history_dir,
            source=args.source,
            exclude_source=args.exclude_source,
            stdout=args.stdout,
            timeout=args.timeout,
        )
        if _errors:
            errors.append(_errors)
    if errors:
        # TODO: add option for a summary/report.
        sys.exit(1)
    else:
        sys.exit(0)
