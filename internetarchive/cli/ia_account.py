"""
ia_account.py

'ia' subcommand for configuring 'ia' with your archive.org credentials.
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

import argparse
import json
import sys

from internetarchive import configure
from internetarchive.account import Account
from internetarchive.exceptions import AccountAPIError


def setup(subparsers):
    """
    Setup args for configure command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("account",
                                   aliases=["ac"],
                                   help=("Manage an archive.org account. "
                                         "Note: requires admin privileges"))

    group = parser.add_mutually_exclusive_group()
    parser.add_argument("user",
                        help="Email address or screenname for an archive.org account")
    group.add_argument("--get-email", "-g",
                        action="store_true",
                        help="Print the email address associated with the user and exit")
    group.add_argument("--get-screenname", "-s",
                        action="store_true",
                        help="Print the screenname associated with the user and exit")
    group.add_argument("--get-itemname", "-i",
                        action="store_true",
                        help="Print the itemname associated with the user and exit")
    group.add_argument("--is-locked", "-l",
                        action="store_true",
                        help="Check if an account is locked")

    parser.set_defaults(func=main)


def main(args: argparse.Namespace) -> None:
    """
    Main entrypoint for 'ia accounts'.
    """
    try:
        if args.user.startswith('@') or '@' not in args.user:
            account = Account.from_screenname(args.user.lstrip('@'))
        else:
            account = Account.from_email(args.user)
    except AccountAPIError as exc:
        print(json.dumps(exc.error_data))
        sys.exit(1)

    if args.get_email:
        print(account.canonical_email)
    elif args.get_screenname:
        print(account.screenname)
    elif args.get_itemname:
        print(account.itemname)
    elif args.is_locked:
        print(account.locked)
    else:
        account_data = dict(account)
        print(json.dumps(account_data))
