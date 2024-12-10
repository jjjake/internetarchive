"""
ia_delete.py

'ia' subcommand for deleting files from archive.org items.
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

import argparse
import sys

import requests.exceptions

from internetarchive.cli.cli_utils import (
    prepare_args_dict,
    validate_identifier,
)
from internetarchive.utils import get_s3_xml_text


def setup(subparsers):
    """
    Setup args for delete command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("delete",
                                   aliases=["rm"],
                                   help="Delete files from archive.org items")
    # Positional arguments
    parser.add_argument("identifier",
                        type=validate_identifier,
                        help="Identifier for the item from which files are to be deleted.")
    parser.add_argument("file",
                        type=str,
                        nargs="*",
                        help="Specific file(s) to delete.")

    # Optional arguments
    parser.add_argument("-q", "--quiet",
                        action="store_true",
                        help="Print status to stdout.")
    parser.add_argument("-c", "--cascade",
                        action="store_true",
                        help="Delete all associated files including derivatives and the original.")
    parser.add_argument("-H", "--header",
                        nargs="+",
                        metavar="KEY:VALUE",
                        action="append",
                        help="S3 HTTP headers to send with your request.")
    parser.add_argument("-a", "--all",
                        action="store_true",
                        help="Delete all files in the given item. Some files cannot be deleted.")
    parser.add_argument("-d", "--dry-run",
                        action="store_true",
                        help=("Output files to be deleted to stdout, "
                              "but don't actually delete them."))
    parser.add_argument("-g", "--glob",
                        type=str,
                        help="Only delete files matching the given pattern.")
    parser.add_argument("-f", "--format",
                        type=str,
                        action="append",
                        help="Only delete files matching the specified formats.")
    parser.add_argument("-R", "--retries",
                        type=int,
                        default=2,
                        help="Number of retries on S3 503 SlowDown error.")
    parser.add_argument("--no-backup",
                        action="store_true",
                        help="Turn off archive.org backups. Clobbered files will not be saved.")

    parser.set_defaults(func=lambda args: main(args, parser))


def get_files_to_delete(args: argparse.Namespace, item) -> list:
    """Get files to delete based on command-line arguments."""
    if args.all:
        files = list(item.get_files())
        args.cascade = True
    elif args.glob:
        files = item.get_files(glob_pattern=args.glob)
    elif args.format:
        files = item.get_files(formats=args.format)
    else:
        fnames = [f.strip() for f in (sys.stdin if args.file == ["-"] else args.file)]
        files = list(item.get_files(fnames))
    return files


def delete_files(files, args, item, verbose):
    """
    Deletes files from an item.

    Args:
        files (list): A list of files to delete.
        args (argparse.Namespace): Parsed command-line arguments.
        item: The item from which files are being deleted.
        verbose (bool): If True, verbose output is enabled.

    Returns:
        bool: True if errors occurred during deletion, False otherwise.
    """
    errors = False

    # Files that cannot be deleted via S3.
    no_delete = ["_meta.xml", "_files.xml", "_meta.sqlite"]

    for f in files:
        if not f:
            if verbose:
                print(f" error: '{f.name}' does not exist", file=sys.stderr)
            errors = True
            continue
        if any(f.name.endswith(s) for s in no_delete):
            continue
        if args.dry_run:
            print(f" will delete: {item.identifier}/{f.name}", file=sys.stderr)
            continue
        try:
            resp = f.delete(verbose=verbose,
                            cascade_delete=args.cascade,
                            headers=args.header,
                            retries=args.retries)
        except requests.exceptions.RetryError:
            print(f" error: max retries exceeded for {f.name}", file=sys.stderr)
            errors = True
            continue

        if resp.status_code != 204:
            errors = True
            msg = get_s3_xml_text(resp.content)
            print(f" error: {msg} ({resp.status_code})", file=sys.stderr)
            continue
    return errors


def main(args: argparse.Namespace, parser: argparse.ArgumentParser):
    """
    Main entry point for 'ia delete'.
    """
    args.header = prepare_args_dict(args.header, parser, arg_type="header")

    verbose = not args.quiet
    item = args.session.get_item(args.identifier)
    if not item.exists:
        print(f"{item.identifier}: skipping, item doesn't exist.", file=sys.stderr)
        return

    # Add keep-old-version by default.
    if "x-archive-keep-old-version" not in args.header and not args.no_backup:
        args.header["x-archive-keep-old-version"] = "1"

    if verbose:
        print(f"Deleting files from {item.identifier}", file=sys.stderr)

    files = get_files_to_delete(args, item)

    if not files:
        print(" warning: no files found, nothing deleted.", file=sys.stderr)
        sys.exit(1)

    errors = delete_files(files, args, item, verbose)

    if errors:
        sys.exit(1)
