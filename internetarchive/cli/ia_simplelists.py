"""
ia_simplelists.py

'ia' subcommand for managing simplelists on archive.org.
"""

# Copyright (C) 2012-2025 Internet Archive
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

from internetarchive.utils import json


def setup(subparsers):
    """Set up argument parser for the 'simplelists' subcommand.

    Args:
        subparsers: argparse subparsers object from main CLI
    """
    parser = subparsers.add_parser("simplelists",
                                   aliases=["sl"],
                                   help="Manage simplelists")
    parser.add_argument(
        "identifier",
        nargs="?",
        type=str,
        help="Identifier for the upload"
    )

    group = parser.add_argument_group("List operations")
    group.add_argument(
        "-p", "--list-parents",
        action="store_true",
        help="List parent lists for the given identifier"
    )
    group.add_argument(
        "-c", "--list-children",
        action="store_true",
        help="List children in parent list"
    )
    group.add_argument(
        "-l", "--list-name",
        type=str,
        help="Name of the list to operate on"
    )

    group = parser.add_argument_group("Modification operations")
    group.add_argument(
        "-s", "--set-parent",
        metavar="PARENT",
        type=str,
        help="Add identifier to specified parent list"
    )
    group.add_argument(
        "-n", "--notes",
        metavar="NOTES",
        type=str,
        help="Notes to attach to the list membership"
    )
    group.add_argument(
        "-r", "--remove-parent",
        metavar="PARENT",
        type=str,
        help="Remove identifier from specified parent list"
    )

    parser.set_defaults(func=lambda args: main(args, parser))


def submit_patch(patch, args):
    """Submit patch request to simplelists API"""
    data = {"-patch": json.dumps(patch), "-target": "simplelists"}
    url = f"{args.session.protocol}//{args.session.host}/metadata/{args.identifier}"
    return args.session.post(url, data=data)


def _handle_patch_operation(args, parser, operation):
    """Handle set/delete patch operations for simplelists.

    :param operation: The patch operation type ('set' or 'delete')
    """
    if not args.identifier:
        parser.error("Missing required identifier argument")
    if not args.list_name:
        parser.error("Must specify list name with -l/--list-name")

    patch = {
        "op": operation,
        "parent": args.set_parent or args.remove_parent,
        "list": args.list_name,
    }
    if args.notes:
        patch["notes"] = args.notes

    r = submit_patch(patch, args)
    try:
        r.raise_for_status()
        print(f"success: {args.identifier}")
    except Exception as e:
        print(f"error: {args.identifier} - {e!s}", file=sys.stderr)
        sys.exit(1)


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Handle simplelists subcommand execution.

    Args:

        args: Parsed command-line arguments
        parser: Argument parser for error handling
    """
    if args.list_parents:
        item = args.session.get_item(args.identifier)
        simplelists = item.item_metadata.get("simplelists")
        if simplelists:
            print(json.dumps(simplelists))
    elif args.list_children:
        args.list_name = args.list_name or "catchall"
        query = f"simplelists__{args.list_name}:{args.identifier or '*'}"
        for result in args.session.search_items(query):
            print(json.dumps(result))

    elif args.set_parent:
        _handle_patch_operation(args, parser, "set")

    elif args.remove_parent:
        _handle_patch_operation(args, parser, "delete")
    else:
        parser.print_help()
        sys.exit(1)
