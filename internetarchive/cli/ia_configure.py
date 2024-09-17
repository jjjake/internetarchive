"""
ia_configure.py

'ia' subcommand for configuring 'ia' with your archive.org credentials.
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
import netrc
import sys

from internetarchive import configure
from internetarchive.exceptions import AuthenticationError


def setup(subparsers):
    """
    Setup args for configure command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("configure",
                                   aliases=["co"],
                                   help=("configure 'ia' with your "
                                         "archive.org credentials"))
    parser.add_argument("--username", "-u",
                        help=("provide username as an option rather than "
                              "providing it interactively"))
    parser.add_argument("--password", "-p",
                        help=("provide password as an option rather than "
                              "providing it interactively"))
    parser.add_argument("--netrc", "-n",
                        action="store_true",
                        help="use netrc file for login")
    parser.add_argument("--print-cookies", "-c",
                        action="store_true",
                        help="print archive.org logged-in-* cookies")

    parser.set_defaults(func=main)


def main(args: argparse.Namespace) -> None:
    """
    Main entrypoint for 'ia configure'.
    """
    if args.print_cookies:
        user = args.session.config.get("cookies", {}).get("logged-in-user")
        sig = args.session.config.get("cookies", {}).get("logged-in-sig")
        if not user or not sig:
            if not user and not sig:
                print("error: 'logged-in-user' and 'logged-in-sig' cookies "
                      "not found in config file, try reconfiguring.", file=sys.stderr)
            elif not user:
                print("error: 'logged-in-user' cookie not found in config file, "
                      "try reconfiguring.", file=sys.stderr)
            elif not sig:
                print("error: 'logged-in-sig' cookie not found in config file, "
                      "try reconfiguring.", file=sys.stderr)
            sys.exit(1)
        print(f"logged-in-user={user}; logged-in-sig={sig}")
        sys.exit()
    try:
        # Netrc
        if args.netrc:
            print("Configuring 'ia' with netrc file...", file=sys.stderr)
            try:
                n = netrc.netrc()
            except netrc.NetrcParseError:
                print("error: netrc.netrc() cannot parse your .netrc file.",
                      file=sys.stderr)
                sys.exit(1)
            except FileNotFoundError:
                print("error: .netrc file not found.", file=sys.stderr)
                sys.exit(1)
            username, _, password = n.hosts["archive.org"]
            config_file_path = configure(username,
                                         password or "",
                                         config_file=args.session.config_file,
                                         host=args.session.host)
            print(f"Config saved to: {config_file_path}", file=sys.stderr)
        # Interactive input.
        else:
            if not (args.username and args.password):
                print("Enter your Archive.org credentials below to configure 'ia'.\n")
            config_file_path = configure(args.username,
                                         args.password,
                                         config_file=args.session.config_file,
                                         host=args.session.host)
            saved_msg = f"Config saved to: {config_file_path}"
            if not all([args.username, args.password]):
                saved_msg = f"\n{saved_msg}"
            print(saved_msg)

    except AuthenticationError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        sys.exit(1)
