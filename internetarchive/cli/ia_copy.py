#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2021 Internet Archive
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

"""Copy files in archive.org items.

usage:
    ia copy <src-identifier>/<src-file> <dest-identifier>/<dest-file> [options]...
    ia copy --help

options:
    -h, --help
    -m, --metadata=<key:value>...  Metadata to add to your new item, if you are moving
                                   the file to a new item.
    --replace-metadata             Only use metadata specified as argument,
                                   do not copy any from the source item.
    -H, --header=<key:value>...    S3 HTTP headers to send with your request.
    --ignore-file-metadata         Do not copy file metadata.
    -n, --no-derive                Do not derive uploaded files.
    --no-backup                    Turn off archive.org backups. Clobbered files
                                   will not be saved to history/files/$key.~N~
                                   [default: True].
"""
from __future__ import annotations

import sys
from urllib.parse import quote

from docopt import docopt, printable_usage
from requests import Response
from schema import And, Or, Schema, SchemaError, Use  # type: ignore[import]

import internetarchive as ia
from internetarchive.cli.argparser import get_args_dict
from internetarchive.utils import get_s3_xml_text, merge_dictionaries


def assert_src_file_exists(src_location: str) -> bool:
    assert SRC_ITEM.exists  # type: ignore
    global SRC_FILE
    src_filename = src_location.split('/', 1)[-1]
    SRC_FILE = SRC_ITEM.get_file(src_filename)  # type: ignore
    assert SRC_FILE.exists  # type: ignore
    return True


def main(
    argv: list[str] | None, session: ia.session.ArchiveSession, cmd: str = 'copy'
) -> tuple[Response, ia.files.File]:
    args = docopt(__doc__, argv=argv)
    src_path = args['<src-identifier>/<src-file>']
    dest_path = args['<dest-identifier>/<dest-file>']

    # If src == dest, file gets deleted!
    try:
        assert src_path != dest_path
    except AssertionError:
        print('error: The source and destination files cannot be the same!',
              file=sys.stderr)
        sys.exit(1)

    global SRC_ITEM
    SRC_ITEM = session.get_item(src_path.split('/')[0])  # type: ignore

    # Validate args.
    s = Schema({
        str: Use(bool),
        '<src-identifier>/<src-file>': And(str, And(And(str, lambda x: '/' in x,
            error='Destination not formatted correctly. See usage example.'),
            assert_src_file_exists, error=(
            f'https://{session.host}/download/{src_path} does not exist. '
            'Please check the identifier and filepath and retry.'))),
        '<dest-identifier>/<dest-file>': And(str, lambda x: '/' in x,
            error='Destination not formatted correctly. See usage example.'),
        '--metadata': Or(None, And(Use(get_args_dict), dict),
                         error='--metadata must be formatted as --metadata="key:value"'),
        '--replace-metadata': Use(bool),
        '--header': Or(None, And(Use(get_args_dict), dict),
                       error='--header must be formatted as --header="key:value"'),
        '--ignore-file-metadata': Use(bool),
    })

    try:
        args = s.validate(args)
    except SchemaError as exc:
        # This module is sometimes called by other modules.
        # Replace references to 'ia copy' in ___doc__ to 'ia {cmd}' for clarity.
        usage = printable_usage(__doc__.replace('ia copy', f'ia {cmd}'))
        print(f'{exc}\n{usage}', file=sys.stderr)
        sys.exit(1)

    args['--header']['x-amz-copy-source'] = f'/{quote(src_path)}'
    # Copy the old metadata verbatim if no additional metadata is supplied,
    # else combine the old and the new metadata in a sensible manner.
    if args['--metadata'] or args['--replace-metadata']:
        args['--header']['x-amz-metadata-directive'] = 'REPLACE'
    else:
        args['--header']['x-amz-metadata-directive'] = 'COPY'

    # New metadata takes precedence over old metadata.
    if not args['--replace-metadata']:
        args['--metadata'] = merge_dictionaries(SRC_ITEM.metadata,  # type: ignore
                                                args['--metadata'])

    # File metadata is copied by default but can be dropped.
    file_metadata = None if args['--ignore-file-metadata'] else SRC_FILE.metadata  # type: ignore

    # Add keep-old-version by default.
    if not args['--header'].get('x-archive-keep-old-version') and not args['--no-backup']:
        args['--header']['x-archive-keep-old-version'] = '1'

    url = f'{session.protocol}//s3.us.archive.org/{quote(dest_path)}'
    queue_derive = True if args['--no-derive'] is False else False
    req = ia.iarequest.S3Request(url=url,
                                 method='PUT',
                                 metadata=args['--metadata'],
                                 file_metadata=file_metadata,
                                 headers=args['--header'],
                                 queue_derive=queue_derive,
                                 access_key=session.access_key,
                                 secret_key=session.secret_key)
    p = req.prepare()
    r = session.send(p)
    if r.status_code != 200:
        try:
            msg = get_s3_xml_text(r.text)
        except Exception as e:
            msg = r.text
        print(f'error: failed to {cmd} "{src_path}" to "{dest_path}" - {msg}', file=sys.stderr)
        sys.exit(1)
    elif cmd == 'copy':
        print(f'success: copied "{src_path}" to "{dest_path}".', file=sys.stderr)
    return (r, SRC_FILE)  # type: ignore
