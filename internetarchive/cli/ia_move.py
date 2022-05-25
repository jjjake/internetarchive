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

"""Move and rename files in archive.org items.

usage:
    ia move <src-identifier>/<src-file> <dest-identifier>/<dest-file> [options]...
    ia move --help

options:
    -h, --help
    -m, --metadata=<key:value>...  Metadata to add to your new item, if you are moving
                                   the file to a new item.
    -H, --header=<key:value>...    S3 HTTP headers to send with your request.
    -n, --no-derive                Do not derive uploaded files.
    --no-backup                    Turn off archive.org backups. Clobbered files
                                   will not be saved to history/files/$key.~N~
                                   [default: True].
"""
import sys

from docopt import docopt, printable_usage
from schema import And, Or, Schema, SchemaError, Use  # type: ignore[import]

from internetarchive import ArchiveSession
from internetarchive.cli import ia_copy
from internetarchive.cli.argparser import get_args_dict


def main(argv, session: ArchiveSession) -> None:
    args = docopt(__doc__, argv=argv)
    src_path = args['<src-identifier>/<src-file>']
    dest_path = args['<dest-identifier>/<dest-file>']

    # Validate args.
    s = Schema({
        str: Use(bool),
        '--metadata': list,
        '--header': Or(None, And(Use(get_args_dict), dict),
            error='--header must be formatted as --header="key:value"'),
        '<src-identifier>/<src-file>': And(str, lambda x: '/' in x,
            error='Source not formatted correctly. See usage example.'),
        '<dest-identifier>/<dest-file>': And(str, lambda x: '/' in x,
            error='Destination not formatted correctly. See usage example.'),
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print(f'{exc}\n{printable_usage(__doc__)}', file=sys.stderr)
        sys.exit(1)

    # Add keep-old-version by default.
    if not args['--header'].get('x-archive-keep-old-version') and not args['--no-backup']:
        args['--header']['x-archive-keep-old-version'] = '1'

    # First we use ia_copy, prep argv for ia_copy.
    argv.pop(0)
    argv = ['copy'] + argv

    # Call ia_copy.
    r, src_file = ia_copy.main(argv, session, cmd='move')
    dr = src_file.delete(headers=args['--header'], cascade_delete=True)
    if dr.status_code == 204:
        print(f'success: moved {src_path} to {dest_path}', file=sys.stderr)
        sys.exit(0)
    print(f'error: {dr.content}', file=sys.stderr)
