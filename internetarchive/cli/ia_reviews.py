"""
ia_reviews.py

'ia' subcommand for listing, submitting, and deleting reviews for archive.org items.
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

from requests.exceptions import HTTPError

from internetarchive.cli.cli_utils import validate_identifier


def setup(subparsers):
    """
    Setup args for list command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("reviews",
                                   aliases=["re"],
                                   help="submit and modify reviews for archive.org items")

    # Positional arguments
    parser.add_argument("identifier",
                        type=validate_identifier,
                        help="identifier of the item")

    # Options
    parser.add_argument("-d", "--delete",
                        action="store_true",
                        help="delete your review")
    parser.add_argument("-t", "--title",
                        type=str,
                        help="the title of your review")
    parser.add_argument("-b", "--body",
                        type=str,
                        help="the body of your review")
    parser.add_argument("-s", "--stars",
                        type=int,
                        help="the number of stars for your review")

    # Conditional arguments that require --delete
    delete_group = parser.add_argument_group("delete options",
                                             ("these options are used with "
                                              "the --delete flag"))
    delete_group.add_argument("-u", "--username",
                              type=str,
                              help="delete reviews for a specific user given USERNAME")
    delete_group.add_argument("-S", "--screenname",
                              type=str,
                              help="delete reviews for a specific user given SCREENNAME")
    delete_group.add_argument("-I", "--itemname",
                              type=str,
                              help="delete reviews for a specific user given ITEMNAME")

    parser.set_defaults(func=lambda args: main(args, parser))


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Main entry point for 'ia reviews'.
    """
    item = args.session.get_item(args.identifier)
    if args.delete:
        r = item.delete_review(username=args.username,
                               screenname=args.screenname,
                               itemname=args.itemname)
    elif not args.body and not args.title:
        try:
            r = item.get_review()
            print(r.text)
            sys.exit(0)
        except HTTPError as exc:
            if exc.response.status_code == 404:  # type: ignore
                sys.exit(0)
            else:
                raise exc
    else:
        if (args.title and not args.body) or (args.body and not args.title):
            parser.error("both --title and --body must be provided")
        r = item.review(args.title, args.body, args.stars)
    j = r.json()
    if j.get("success") or "no change detected" in j.get("error", "").lower():
        task_id = j.get("value", {}).get("task_id")
        if task_id:
            print((f"{item.identifier} - success: "
                   f"https://catalogd.archive.org/log/{task_id}"),
                  file=sys.stderr)
        else:
            print(f"{item.identifier} - warning: no changes detected!", file=sys.stderr)
        sys.exit(0)
    else:
        print(f"{item.identifier} - error: {j.get('error')}", file=sys.stderr)
        sys.exit(1)
