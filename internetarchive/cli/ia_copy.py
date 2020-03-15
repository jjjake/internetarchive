# -*- coding: utf-8 -*-
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

"""Copy files in archive.org items.

usage:
    ia copy <src-identifier>/<src-file> <dest-identifier>/<dest-file> [options]...
    ia copy --help

options:
    -h, --help
    -m, --metadata=<key:value>...  Metadata to add to your new item, if you are moving
                                   the file to a new item.
    -H, --header=<key:value>...    S3 HTTP headers to send with your request.

examples:
    # Turn off backups
    ia copy <src-identifier>/<src-file> <dest-identifier>/<dest-file> -H x-archive-keep-old-version:0
"""
from __future__ import print_function, absolute_import
import sys

from docopt import docopt, printable_usage
from schema import Schema, Use, Or, And, SchemaError
from six.moves.urllib import parse

import internetarchive as ia
from internetarchive.cli.argparser import get_args_dict
from internetarchive.utils import get_s3_xml_text


def assert_src_file_exists(src_location):
    assert SRC_ITEM.exists
    global SRC_FILE
    src_filename = src_location.split('/', 1)[-1]
    SRC_FILE = SRC_ITEM.get_file(src_filename)
    assert SRC_FILE.exists
    return True


def main(argv, session, cmd='copy'):
    args = docopt(__doc__, argv=argv)
    src_path = args['<src-identifier>/<src-file>']
    dest_path = args['<dest-identifier>/<dest-file>']

    # If src == dest, file get's deleted!
    try:
        assert src_path != dest_path
    except AssertionError:
        print('error: The source and destination files cannot be the same!',
              file=sys.stderr)
        sys.exit(1)

    global SRC_ITEM
    SRC_ITEM = session.get_item(src_path.split('/')[0])

    # Validate args.
    s = Schema({
        str: Use(bool),
        '<src-identifier>/<src-file>': And(str, And(And(str, lambda x: '/' in x,
            error='Destination not formatted correctly. See usage example.'),
            assert_src_file_exists, error=(
            'https://{}/download/{} does not exist. '
            'Please check the identifier and filepath and retry.'.format(session.host,
                                                                         src_path)))),
        '<dest-identifier>/<dest-file>': And(str, lambda x: '/' in x,
            error='Destination not formatted correctly. See usage example.'),
        '--metadata': Or(None, And(Use(get_args_dict), dict),
                         error='--metadata must be formatted as --metadata="key:value"'),
        '--header': Or(None, And(Use(get_args_dict), dict),
                       error='--header must be formatted as --header="key:value"'),
    })

    try:
        args = s.validate(args)
    except SchemaError as exc:
        # This module is sometimes called by other modules.
        # Replace references to 'ia copy' in ___doc__ to 'ia {cmd}' for clarity.
        usage = printable_usage(__doc__.replace('ia copy', 'ia {}'.format(cmd)))
        print('{0}\n{1}'.format(str(exc), usage), file=sys.stderr)
        sys.exit(1)

    args['--header']['x-amz-copy-source'] = '/{}'.format(parse.quote(src_path))
    args['--header']['x-amz-metadata-directive'] = 'COPY'
    # Add keep-old-version by default.
    if 'x-archive-keep-old-version' not in args['--header']:
        args['--header']['x-archive-keep-old-version'] = '1'

    url = '{}//s3.us.archive.org/{}'.format(session.protocol, parse.quote(dest_path))
    req = ia.iarequest.S3Request(url=url,
                                 method='PUT',
                                 metadata=args['--metadata'],
                                 headers=args['--header'],
                                 access_key=session.access_key,
                                 secret_key=session.secret_key)
    p = req.prepare()
    r = session.send(p)
    if r.status_code != 200:
        try:
            msg = get_s3_xml_text(r.text)
        except Exception as e:
            msg = r.text
        print('error: failed to {} "{}" to "{}" - {}'.format(
            cmd, src_path, dest_path, msg))
        sys.exit(1)
    elif cmd == 'copy':
        print('success: copied "{}" to "{}".'.format(src_path, dest_path))
    else:
        return (r, SRC_FILE)
