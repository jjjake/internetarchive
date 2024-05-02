"""
ia_list.py

'ia' subcommand for listing files from archive.org items.
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
import csv
import sys
from fnmatch import fnmatch
from itertools import chain

from internetarchive.cli.cli_utils import validate_identifier


def setup(subparsers):
    """
    Setup args for list command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("list",
                                   aliases=["ls"],
                                   help="list files from archive.org items")

    # Positional arguments
    parser.add_argument("identifier",
                        type=validate_identifier,
                        help="identifier of the item")

    # Options
    parser.add_argument("-v", "--verbose",
                        action="store_true",
                        help="print column headers")
    parser.add_argument("-a", "--all",
                        action="store_true",
                        help="list all information available for files")
    parser.add_argument("-l", "--location",
                        action="store_true",
                        help="print full URL for each file")
    parser.add_argument("-c", "--columns",
                        action="append",
                        type=prepare_columns,
                        help="list specified file information")
    parser.add_argument("-g", "--glob",
                        help="only return files matching the given pattern")
    parser.add_argument("-f", "--format",
                        action="append",
                        help="return files matching FORMAT")

    parser.set_defaults(func=main)


def prepare_columns(columns):
    """
    Validate the path to the configuration file.

    Returns:
        str: Validated list of columns
    """
    if columns:
        if not isinstance(columns, list):
            columns = [columns]
        return list(chain.from_iterable([c.split(",") for c in columns]))
    return None


def setup_columns(args, files):
    """
    Setup and adjust columns for output based on args.
    """
    if not args.columns:
        args.columns = ["name"]
    else:
        args.columns = list(chain.from_iterable(args.columns))

    if args.all:
        args.columns = list(set(chain.from_iterable(k for k in files)))

    # Make "name" the first column always.
    if "name" in args.columns:
        args.columns.remove("name")
        args.columns.insert(0, "name")


def filter_files(args, files, item):
    """
    Filter files based on glob patterns or formats.
    """
    if args.glob:
        patterns = args.glob.split("|")
        return [f for f in files if any(fnmatch(f["name"], p) for p in patterns)]
    if args.format:
        return [f.__dict__ for f in item.get_files(formats=args.format)]
    return files


def generate_output(files, args, dict_writer, item):
    """
    Generate and write output based on filtered files and columns.
    """
    output = []
    for f in files:
        file_dict = {}
        for key, val in f.items():
            if key in args.columns:
                if isinstance(val, (list, tuple, set)):
                    val = ";".join(val)
                if key == "name" and args.location:
                    file_dict[key] = (f"https://{args.session.host}"
                                      f"/download/{item.identifier}/{val}")
                else:
                    file_dict[key] = val
        output.append(file_dict)
    if args.verbose:
        dict_writer.writer.writerow(args.columns)
    if all(x == {} for x in output):
        sys.exit(1)
    dict_writer.writerows(output)


def main(args: argparse.Namespace) -> None:
    """
    Main entry point for 'ia list'.
    """
    item = args.session.get_item(args.identifier)
    files = item.files

    setup_columns(args, files)
    files = filter_files(args, files, item)

    dict_writer = csv.DictWriter(sys.stdout, args.columns,
                                 delimiter="\t",
                                 lineterminator="\n")
    generate_output(files, args, dict_writer, item)
