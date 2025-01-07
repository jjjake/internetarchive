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
from internetarchive.utils import is_valid_email


def setup(subparsers):
    """
    Setup args for configure command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("account",
                                   aliases=["ac"],
                                   description=(
                                       "Manage an archive.org account.\n\n"
                                       "Note: This command requires administrative "
                                       "privileges. "
                                   ),
                                   help=("Manage an archive.org account. "
                                         "Note: requires admin privileges"))

    group = parser.add_mutually_exclusive_group()
    parser.add_argument("user",
                        help="Email address, screenname, or itemname "
                             "for an archive.org account")
    group.add_argument("-g", "--get-email",
                        action="store_true",
                        help="Print the email address associated with the user and exit")
    group.add_argument("-s", "--get-screenname",
                        action="store_true",
                        help="Print the screenname associated with the user and exit")
    group.add_argument("-i", "--get-itemname",
                        action="store_true",
                        help="Print the itemname associated with the user and exit")
    group.add_argument("-l", "--is-locked",
                        action="store_true",
                        help="Check if an account is locked")
    group.add_argument("-L", "--lock",
                        action="store_true",
                        help="Lock an account")
    group.add_argument("-u", "--unlock",
                        action="store_true",
                        help="Unlock an account")

    parser.add_argument("-c", "--comment",
                        type=str,
                        help="Comment to include with lock/unlock action")

    parser.set_defaults(func=main)


def main(args: argparse.Namespace) -> None:
    """
    Main entrypoint for 'ia account'.
    """
    try:
        if args.user.startswith('@'):
            account = Account.from_account_lookup('itemname', args.user)
        elif not is_valid_email(args.user):
            account = Account.from_account_lookup('screenname', args.user)
        else:
            account = Account.from_account_lookup('email', args.user)
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
    elif args.lock:
        r = account.lock("test lock", session=args.session)
        print(r.text)
    elif args.unlock:
        r = account.unlock("test unlock", session=args.session)
        print(r.text)
    else:
        account_data = account.to_dict()
        print(json.dumps(account_data))
