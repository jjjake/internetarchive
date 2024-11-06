"""
ia_search.py

'ia' subcommand for searching items on archive.org.
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
from itertools import chain

from requests.exceptions import ConnectTimeout, ReadTimeout

from internetarchive.cli.cli_utils import prepare_args_dict
from internetarchive.exceptions import AuthenticationError
from internetarchive.utils import json


def setup(subparsers):
    """
    Setup args for search command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("search",
                                   aliases=["se"],
                                   help="Search items on archive.org")

    # Positional arguments
    parser.add_argument("query",
                        type=str,
                        help="Search query or queries.")

    # Optional arguments
    parser.add_argument("-p", "--parameters",
                        nargs="+",
                        metavar="KEY:VALUE",
                        action="append",
                        help="Parameters to send with your query.")
    parser.add_argument("-H", "--header",
                        nargs="+",
                        metavar="KEY:VALUE",
                        action="append",
                        help="Add custom headers to your search request.")
    parser.add_argument("-s", "--sort",
                        action="append",
                        help="Sort search results by specified fields.")
    parser.add_argument("-i", "--itemlist",
                        action="store_true",
                        help="Output identifiers only.")
    parser.add_argument("-f", "--field",
                        action="append",
                        help="Metadata fields to return.")
    parser.add_argument("-n", "--num-found",
                        action="store_true",
                        help="Print the number of results to stdout.")
    parser.add_argument("-F", "--fts",
                        action="store_true",
                        help="Beta support for querying the archive.org full text search API.")
    parser.add_argument("-D", "--dsl-fts",
                        action="store_true",
                        help="Submit --fts query in dsl.")
    parser.add_argument("-t", "--timeout",
                        type=float,
                        default=300,
                        help="Set the timeout in seconds.")


    parser.set_defaults(func=lambda args: main(args, parser))


def prepare_values(value):
    """
    Prepare comma-separated values based on the input value.
    """
    if value:
        return list(chain.from_iterable([x.split(",") for x in value]))
    return None


def perform_search(args, fields, sorts, r_kwargs):
    """
    Perform the search using the provided arguments and request kwargs.
    """
    return args.session.search_items(args.query,  # type: ignore
                                     fields=fields,
                                     sorts=sorts,
                                     params=args.parameters,
                                     full_text_search=args.fts,
                                     dsl_fts=args.dsl_fts,
                                     request_kwargs=r_kwargs)


def handle_search_results(args, search):
    """
    Handle search results based on command-line arguments.
    """
    if args.num_found:
        print(search.num_found)
        sys.exit(0)

    for result in search:
        if args.itemlist:
            if args.fts or args.dsl_fts:
                print("\n".join(result.get("fields", {}).get("identifier")))
            else:
                print(result.get("identifier", ""))
        else:
            print(json.dumps(result))
            if result.get("error"):
                sys.exit(1)


def handle_value_error(exc):
    """
    Handle ValueError exception.
    """
    return f"error: {exc}"


def handle_connect_timeout():
    """
    Handle ConnectTimeout exception.
    """
    return "error: Request timed out. Increase the --timeout and try again."


def handle_read_timeout():
    """
    Handle ReadTimeout exception.
    """
    return "error: The server timed out and failed to return all search results, please try again"


def handle_authentication_error(exc):
    """
    Handle AuthenticationError exception.
    """
    return f"error: {exc}"


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Main entry point for 'ia search'.
    """
    try:
        # Validate args.
        args.parameters = prepare_args_dict(args.parameters,
                                            parser=parser,
                                            arg_type='parameters',
                                            query_string=True)
        args.header = prepare_args_dict(args.header,
                                        parser=parser,
                                        arg_type='header')

        # Prepare fields and sorts.
        fields = prepare_values(args.field)
        sorts = prepare_values(args.sort)

        # Prepare request kwargs.
        r_kwargs = {
            "headers": args.header,
            "timeout": args.timeout,
        }

        # Perform search.
        search = perform_search(args, fields, sorts, r_kwargs)

        # Handle search results.
        handle_search_results(args, search)

    except ValueError as exc:
        error_message = handle_value_error(exc)
        print(error_message, file=sys.stderr)
        sys.exit(1)

    except ConnectTimeout:
        error_message = handle_connect_timeout()
        print(error_message, file=sys.stderr)
        sys.exit(1)

    except ReadTimeout:
        error_message = handle_read_timeout()
        print(error_message, file=sys.stderr)
        sys.exit(1)

    except AuthenticationError as exc:
        error_message = handle_authentication_error(exc)
        print(error_message, file=sys.stderr)
        sys.exit(1)
