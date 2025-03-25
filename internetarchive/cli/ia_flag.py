"""
ia_flag.py

'ia' subcommand for managing flags on archive.org.
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


def setup(subparsers):
    """Set up argument parser for the 'flag' subcommand.

    Args:
        subparsers: argparse subparsers object from main CLI
    """
    parser = subparsers.add_parser(
        "flag",
        aliases=["fl"],
        help="Manage flags",
    )
    parser.add_argument(
        "identifier",
        nargs="?",
        type=str,
        help="Identifier for the upload",
    )
    parser.add_argument(
        "-u",
        "--user",
        type=str,
        help="User associated with the flag",
    )

    group = parser.add_argument_group("Add flag operations")
    group.add_argument(
        "-a",
        "--add-flag",
        metavar="CATEGORY",
        type=str,
        help="Add a flag to the item",
    )

    group = parser.add_argument_group("Delete flag operations")
    group.add_argument(
        "-d",
        "--delete-flag",
        metavar="CATEGORY",
        type=str,
        help="Delete a flag from the item",
    )

    parser.set_defaults(func=lambda args: main(args, parser))

def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Handle flag subcommand execution.

    Args:
        args: Parsed command-line arguments
        parser: Argument parser for error handling
    """
    item = args.session.get_item(args.identifier)
    if args.user:
        flag_user = args.user
    else:
        flag_user = args.session.config.get("general", {}).get("screenname")
    if not flag_user.startswith('@'):
        flag_user = f"@{flag_user}"
    if args.add_flag:
        r = item.add_flag(args.add_flag, flag_user)
        j = r.json()
        if j.get("status") == "success":
            print(f"success: added '{args.add_flag}' flag by {flag_user} to {args.identifier}")
        else:
            print(f"error: {item.identifier} - {r.text}")

    elif args.delete_flag:
        r = item.delete_flag(args.delete_flag, flag_user)
        j = r.json()
        if j.get("status") == "success":
            print(f"success: deleted '{args.delete_flag}' flag by {flag_user} from {args.identifier}")
        else:
            print(f"error: {item.identifier} - {r.text}")

    else:
        r = item.get_flags()
        print(r.text)
