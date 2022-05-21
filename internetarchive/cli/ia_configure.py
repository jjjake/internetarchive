#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2019 Internet Archive
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

"""Configure 'ia' with your Archive.org credentials.

usage:
    ia configure
    ia configure --username=<username> --password=<password>
    ia configure --print-cookies
    ia configure --netrc
    ia configure [--help]

options:
    -h, --help
    -u, --username=<username>  Provide username as an option rather than
                               providing it interactively.
    -p, --password=<password>  Provide password as an option rather than
                               providing it interactively.
    -n, --netrc                Use netrc file for login.
    -c, --print-cookies        Print archive.org logged-in-* cookies.
"""
from __future__ import annotations

import netrc
import sys

from docopt import docopt

from internetarchive import ArchiveSession, configure
from internetarchive.exceptions import AuthenticationError


def main(argv: list[str], session: ArchiveSession) -> None:
    args = docopt(__doc__, argv=argv)
    if args['--print-cookies']:
        user = session.config.get('cookies', {}).get('logged-in-user')
        sig = session.config.get('cookies', {}).get('logged-in-sig')
        if not user or not sig:
            if not user and not sig:
                print('error: "logged-in-user" and "logged-in-sig" cookies '
                      'not found in config file, try reconfiguring.', file=sys.stderr)
            elif not user:
                print('error: "logged-in-user" cookie not found in config file, '
                      'try reconfiguring.', file=sys.stderr)
            elif not sig:
                print('error: "logged-in-sig" cookie not found in config file, '
                      'try reconfiguring.', file=sys.stderr)
            sys.exit(1)
        print(f'logged-in-user={user}; logged-in-sig={sig}')
        sys.exit()
    try:
        # CLI params.
        if args['--username'] and args['--password']:
            config_file_path = configure(args['--username'],
                                         args['--password'],
                                         config_file=session.config_file,
                                         host=session.host)
            print(f'Config saved to: {config_file_path}', file=sys.stderr)

        # Netrc
        elif args['--netrc']:
            print("Configuring 'ia' with netrc file...", file=sys.stderr)
            try:
                n = netrc.netrc()
            except netrc.NetrcParseError as exc:
                print('error: netrc.netrc() cannot parse your .netrc file.', file=sys.stderr)
                sys.exit(1)
            username, _, password = n.hosts['archive.org']
            config_file_path = configure(username,
                                         password or "",
                                         config_file=session.config_file,
                                         host=session.host)
            print(f'Config saved to: {config_file_path}', file=sys.stderr)

        # Interactive input.
        else:
            print("Enter your Archive.org credentials below to configure 'ia'.\n")
            config_file_path = configure(config_file=session.config_file,
                                         host=session.host)
            print(f'\nConfig saved to: {config_file_path}')

    except AuthenticationError as exc:
        print(f'\nerror: {exc}', file=sys.stderr)
        sys.exit(1)
