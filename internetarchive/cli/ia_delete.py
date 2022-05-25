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

"""Delete files from Archive.org.

usage:
    ia delete <identifier> <file>... [options]...
    ia delete <identifier> [options]...
    ia delete --help

options:
    -h, --help
    -q, --quiet                  Print status to stdout.
    -c, --cascade                Delete all files associated with the specified file,
                                 including upstream derivatives and the original.
                                 file.
    -H, --header=<key:value>...  S3 HTTP headers to send with your request.
    -a, --all                    Delete all files in the given item (Note: Some files,
                                 such as <identifier>_meta.xml and <identifier>_files.xml,
                                 cannot be deleted)
    -d, --dry-run                Output files to be deleted to stdout, but don't actually
                                 delete.
    -g, --glob=<pattern>         Only delete files matching the given pattern.
    -f, --format=<format>...     Only only delete files matching the specified format(s).
    -R, --retries=<i>            Number of times to retry if S3 returns a 503 SlowDown
                                 error [default: 2].
    --no-backup                  Turn off archive.org backups. Clobbered files
                                 will not be saved to history/files/$key.~N~
                                 [default: True].
"""
import sys

import requests.exceptions
from docopt import docopt, printable_usage
from schema import And, Or, Schema, SchemaError, Use  # type: ignore[import]

from internetarchive import ArchiveSession
from internetarchive.cli.argparser import convert_str_list_to_unicode, get_args_dict
from internetarchive.utils import get_s3_xml_text


def main(argv, session: ArchiveSession) -> None:
    args = docopt(__doc__, argv=argv)

    # Validation error messages.
    invalid_id_msg = ('<identifier> should be between 3 and 80 characters in length, and '
                      'can only contain alphanumeric characters, underscores ( _ ), or '
                      'dashes ( - )')

    # Validate args.
    s = Schema({
        str: Use(bool),
        '<file>': list,
        '--format': list,
        '--header': Or(None, And(Use(get_args_dict), dict),
                       error='--header must be formatted as --header="key:value"'),
        '--glob': list,
        'delete': bool,
        '--retries': Use(lambda i: int(i[0])),
        '<identifier>': str,
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print(f'{exc}\n{printable_usage(__doc__)}', file=sys.stderr)
        sys.exit(1)

    verbose = True if not args['--quiet'] else False
    item = session.get_item(args['<identifier>'])
    if not item.exists:
        print('{0}: skipping, item does\'t exist.', file=sys.stderr)

    # Files that cannot be deleted via S3.
    no_delete = ['_meta.xml', '_files.xml', '_meta.sqlite']

    # Add keep-old-version by default.
    if not args['--header'].get('x-archive-keep-old-version') and not args['--no-backup']:
        args['--header']['x-archive-keep-old-version'] = '1'

    if verbose:
        print(f'Deleting files from {item.identifier}', file=sys.stderr)

    if args['--all']:
        files = list(item.get_files())
        args['--cascade'] = True
    elif args['--glob']:
        files = item.get_files(glob_pattern=args['--glob'])
    elif args['--format']:
        files = item.get_files(formats=args['--format'])
    else:
        fnames = []
        if args['<file>'] == ['-']:
            fnames = [f.strip() for f in sys.stdin]
        else:
            fnames = [f.strip() for f in args['<file>']]

        files = list(item.get_files(fnames))

    if not files:
        print(' warning: no files found, nothing deleted.', file=sys.stderr)
        sys.exit(1)

    errors = False

    for f in files:
        if not f:
            if verbose:
                print(f' error: "{f.name}" does not exist', file=sys.stderr)
            errors = True
        if any(f.name.endswith(s) for s in no_delete):
            continue
        if args['--dry-run']:
            print(f' will delete: {item.identifier}/{f.name}', file=sys.stderr)
            continue
        try:
            resp = f.delete(verbose=verbose,
                            cascade_delete=args['--cascade'],
                            headers=args['--header'],
                            retries=args['--retries'])
        except requests.exceptions.RetryError as e:
            print(f' error: max retries exceeded for {f.name}', file=sys.stderr)
            errors = True
            continue

        if resp.status_code != 204:
            errors = True
            msg = get_s3_xml_text(resp.content)
            print(f' error: {msg} ({resp.status_code})', file=sys.stderr)
            continue

    if errors is True:
        sys.exit(1)
