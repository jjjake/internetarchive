"""
ia_move.py

'ia' subcommand for moving files on archive.org
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

from internetarchive.cli import ia_copy
from internetarchive.cli.cli_utils import prepare_args_dict


def setup(subparsers):
    """
    Setup args for move command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("move",
                                   aliases=["mv"],
                                   help="Move and rename files in archive.org items")

    # Positional arguments
    parser.add_argument("source",
                        metavar="SOURCE",
                        help="Source file formatted as: identifier/file")
    parser.add_argument("destination",
                        metavar="DESTINATION",
                        help="Destination file formatted as: identifier/file")

    # Options
    parser.add_argument("-m", "--metadata",
                        metavar="KEY:VALUE",
                        action="append",
                        help=("Metadata to add to your new item, "
                              "if you are moving the file to a new item"))
    parser.add_argument("-H", "--header",
                        metavar="KEY:VALUE",
                        action="append",
                        help="S3 HTTP headers to send with your request")
    parser.add_argument("--replace-metadata",
                        action="store_true",
                        help=("Only use metadata specified as argument, do not copy any "
                              "from the source item"))
    parser.add_argument("--ignore-file-metadata",
                        action="store_true",
                        help="Do not copy file metadata")
    parser.add_argument("-n", "--no-derive",
                        action="store_true",
                        help="Do not derive uploaded files")
    parser.add_argument("--no-backup",
                        action="store_true",
                        help=("Turn off archive.org backups, "
                              "clobbered files will not be saved to 'history/files/$key.~N~'"))

    parser.set_defaults(func=lambda args: main(args, parser))


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Main entry point for ia move command.
    """
    args.header = prepare_args_dict(args.header, parser=parser, arg_type="header")
    args.metadata = prepare_args_dict(args.metadata, parser=parser, arg_type="metadata")

    # Add keep-old-version by default.
    if not args.header.get("x-archive-keep-old-version") and not args.no_backup:
        args.header["x-archive-keep-old-version"] = "1"

    # Call ia_copy.
    _, src_file = ia_copy.main(args, cmd="move", parser=parser)
    if src_file:
        dr = src_file.delete(headers=args.header, cascade_delete=True)
    else:
        print(f"error: {src_file} does not exist", file=sys.stderr)
        sys.exit(1)
    if dr.status_code == 204:
        print(f"success: moved '{args.source}' to '{args.destination}'", file=sys.stderr)
        sys.exit(0)
    print(f"error: {dr.content}", file=sys.stderr)
