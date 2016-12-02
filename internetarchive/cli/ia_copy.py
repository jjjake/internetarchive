# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2016 Internet Archive
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

"""Copy and rename files in archive.org items.

usage:
    ia copy <src-identifier>/<src-file> <dest-identifier>/<dest-file> [options]...
    ia copy --help

options:
    -h, --help
    -m, --metadata=<key:value>...  Metadata to add to your new item, if you are moving
                                   the file to a new item.
"""
from __future__ import print_function, absolute_import
import sys

import six
from docopt import docopt, printable_usage
from schema import Schema, Use, Or, And, SchemaError

import internetarchive as ia
from internetarchive.cli.argparser import get_args_dict


def assert_src_file_exists(src_location):
    assert SRC_ITEM.exists
    global SRC_FILE
    src_filename = src_location.split('/', 1)[-1]
    SRC_FILE = SRC_ITEM.get_file(src_filename)
    assert SRC_FILE.exists
    return True


def main(argv, session, cmd='copy'):
    args = docopt(__doc__, argv=argv)
    global SRC_ITEM
    SRC_ITEM = session.get_item(args['<src-identifier>/<src-file>'].split('/')[0])

    # Validate args.
    s = Schema({
        str: Use(bool),
        '<src-identifier>/<src-file>': And(six.text_type, assert_src_file_exists, error=(
            'https://archive.org/download/{} does not exist. '
            'Please check the identifier and filepath and retry.'.format(
                       args['<src-identifier>/<src-file>']))),
        '<dest-identifier>/<dest-file>': six.text_type,
        '--metadata': Or(None, And(Use(get_args_dict), dict),
                         error='--metadata must be formatted as --metadata="key:value"'),
    })

    try:
        args = s.validate(args)
    except SchemaError as exc:
        # This module is sometimes called by other modules.
        # Replace references to 'ia copy' in ___doc__ to 'ia {cmd}' for clarity.
        sys.stderr.write('{0}\n{1}\n'.format(
            str(exc), printable_usage(__doc__.replace('ia copy', 'ia {}'.format(cmd)))))
        sys.exit(1)

    headers = {
        'x-amz-copy-source': '/{}'.format(args['<src-identifier>/<src-file>']),
        'x-amz-metadata-directive': 'COPY',
    }
    url = '{}//s3.us.archive.org/{}'.format(session.protocol,
                                            args['<dest-identifier>/<dest-file>'])
    req = ia.iarequest.S3Request(url=url,
                                 method='PUT',
                                 metadata=args['--metadata'],
                                 headers=headers,
                                 access_key=session.access_key,
                                 secret_key=session.secret_key)
    p = req.prepare()
    r = session.send(p)
    if r.status_code != 200:
        print('error: failed to {} {} to {}. {}'.format(cmd,
              args['<src-identifier>/<src-file>'], args['<src-identifier>/<src-file>']))
        sys.exit(1)
    elif cmd == 'copy':
        print('success: copied {} to {}.'.format(args['<src-identifier>/<src-file>'],
              args['<dest-identifier>/<dest-file>']))
    else:
        return (r, SRC_FILE)
