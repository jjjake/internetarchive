"""
ia_download.py

'ia' subcommand for downloading files from archive.org.
"""

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

from __future__ import annotations

import argparse
import sys
from typing import TextIO

from internetarchive.cli.cli_utils import prepare_args_dict, validate_dir_path, validate_identifier
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
                                   help="Retrieve and modify archive.org item metadata")

    # Main options
    parser.add_argument("identifier",
                        nargs="?",
                        type=validate_identifier,
                        help="Identifier for the upload")
    parser.add_argument("file",
                        nargs="*",
                        help="Files to download")

    # Additional options
    parser.add_argument("-q", "--quiet",
                        action="store_true",
                        help="Turn off ia's output [default: False]")
    parser.add_argument("-d", "--dry-run",
                        action="store_true",
                        help="Print URLs to stdout and exit")
    parser.add_argument("-i", "--ignore-existing",
                        action="store_true",
                        help="Clobber files already downloaded")
    parser.add_argument("-C", "--checksum",
                        action="store_true",
                        help="Skip files based on checksum [default: False]")
    parser.add_argument("--checksum-archive",
                        action="store_true",
                        help="Skip files based on _checksum_archive.txt file")
    parser.add_argument("-R", "--retries",
                        type=int,
                        default=5,
                        help="Set number of retries to <retries> [default: 5]")
    parser.add_argument("-I", "--itemlist",
                        type=argparse.FileType("r"),
                        help=("Download items from a specified file. "
                             "Itemlists should be a plain text file with one "
                             "identifier per line"))
    parser.add_argument("-S", "--search",
                        help="Download items returned from a specified search query")
    parser.add_argument("-P", "--search-parameters",
                        nargs="+",
                        help="Download items returned from a specified search query")
    parser.add_argument("-g", "--glob",
                        help=("Only download files whose filename matches "
                             "the given glob pattern"))
    parser.add_argument("-e", "--exclude",
                        help=("Exclude files whose filename matches "
                             "the given glob pattern"))
    parser.add_argument("-f", "--format",
                        nargs="+",
                        help=("Only download files of the specified format. "
                             "Use this option multiple times to download "
                             "multiple formats. You can use the following command to "
                             "retrieve a list of file formats contained within a "
                             "given item: ia metadata --formats <identifier>"))
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
                        help=("The destination directory to download files "
                             "and item directories to"))
    parser.add_argument("-s", "--stdout",
                        action="store_true",
                        help="Write file contents to stdout")
    parser.add_argument("--no-change-timestamp",
                        action="store_true",
                        help=("Don't change the timestamp of downloaded files to reflect "
                             "the source material"))
    parser.add_argument("-p", "--parameters",
                        nargs="+",
                        help="Parameters to send with your query (e.g. `cnt=0`)")
    parser.add_argument("-a", "--download-history",
                        action="store_true",
                        help="Also download files from the history directory")
    parser.add_argument("--source",
                        nargs="+",
                        help=("Filter files based on their source value in files.xml "
                             "(i.e. `original`, `derivative`, `metadata`)"))
    parser.add_argument("--exclude-source",
                        nargs="+",
                        help=("Filter files based on their source value in files.xml "
                             "(i.e. `original`, `derivative`, `metadata`)"))
    parser.add_argument("-t", "--timeout",
                        type=float,
                        help=("Set a timeout for download requests. "
                             "This sets both connect and read timeout"))

    parser.set_defaults(func=lambda args: main(args, parser))


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Main entry point for 'ia download'.
    """
    args.parameters = prepare_args_dict(args.parameters,
                                        parser=parser,
                                        arg_type="parameters")
    args.search_parameters = prepare_args_dict(args.search_parameters,
                                               parser=parser,
                                               arg_type="search-parameters")

    ids: list[File | str] | Search | TextIO

    if args.itemlist:
        with open(args.itemlist) as fp:
            ids = [x.strip() for x in fp]
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
        ignore_history_dir = bool(args.download_history)
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
            destdir=args.destdir,
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
