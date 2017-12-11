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

"""Upload files to Archive.org.

usage:
    ia upload <identifier> <file>... [options]...
    ia upload <identifier> - --remote-name=<name> [options]...
    ia upload <identifier> <file> --remote-name=<name> [options]...
    ia upload --spreadsheet=<metadata.csv> [options]...
    ia upload <identifier> --status-check
    ia upload --help

options:
    -h, --help
    -q, --quiet                       Turn off ia's output [default: False].
    -d, --debug                       Print S3 request parameters to stdout and exit
                                      without sending request.
    -r, --remote-name=<name>          When uploading data from stdin, this option sets the
                                      remote filename.
    -S, --spreadsheet=<metadata.csv>  bulk uploading.
    -m, --metadata=<key:value>...     Metadata to add to your item.
    -H, --header=<key:value>...       S3 HTTP headers to send with your request.
    -c, --checksum                    Skip based on checksum. [default: False]
    -v, --verify                      Verify that data was not corrupted traversing the
                                      network. [default: False]
    -n, --no-derive                   Do not derive uploaded files.
    --size-hint=<size>                Specify a size-hint for your item.
    --delete                          Delete files after verifying checksums
                                      [default: False].
    -R, --retries=<i>                 Number of times to retry request if S3 returns a
                                      503 SlowDown error.
    -s, --sleep=<i>                   The amount of time to sleep between retries
                                      [default: 30].
    --status-check                    Check if S3 is accepting requests to the given item.
    --no-collection-check             Skip collection exists check [default: False].
"""
from __future__ import absolute_import, unicode_literals, print_function

import io
from backports import csv
import os
import sys
from tempfile import TemporaryFile
from copy import deepcopy

import six
from docopt import docopt, printable_usage
from requests.exceptions import HTTPError
from schema import Schema, Use, Or, And, SchemaError

from internetarchive.cli.argparser import get_args_dict, convert_str_list_to_unicode
from internetarchive.session import ArchiveSession
from internetarchive.utils import validate_ia_identifier, get_s3_xml_text


def _upload_files(item, files, upload_kwargs, prev_identifier=None, archive_session=None):
    """Helper function for calling :meth:`Item.upload`"""
    responses = []
    if (upload_kwargs['verbose']) and (prev_identifier != item.identifier):
        print('{0}:'.format(item.identifier))

    try:
        response = item.upload(files, **upload_kwargs)
        responses += response
    except HTTPError as exc:
        responses += [exc.response]
    finally:
        # Debug mode.
        if upload_kwargs['debug']:
            for i, r in enumerate(responses):
                if i != 0:
                    print('---')
                headers = '\n'.join(
                    [' {0}:{1}'.format(k, v) for (k, v) in r.headers.items()]
                )
                print('Endpoint:\n {0}\n'.format(r.url))
                print('HTTP Headers:\n{0}'.format(headers))
                return responses

        # Format error message for any non 200 responses that
        # we haven't caught yet,and write to stderr.
        if responses and responses[-1] and responses[-1].status_code != 200:
            if not responses[-1].status_code:
                return responses
            filename = responses[-1].request.url.split('/')[-1]
            try:
                msg = get_s3_xml_text(responses[-1].content)
            except:
                msg = responses[-1].content
            print(' error uploading {0}: {2}'.format(filename, msg), file=sys.stderr)

    return responses


def main(argv, session):
    if six.PY2:
        args = docopt(__doc__.encode('utf-8'), argv=argv)
    else:
        args = docopt(__doc__, argv=argv)
    ERRORS = False

    # Validate args.
    s = Schema({
        str: Use(bool),
        '<identifier>': Or(None, And(str, validate_ia_identifier,
            error=('<identifier> should be between 3 and 80 characters in length, and '
                   'can only contain alphanumeric characters, periods ".", '
                   'underscores "_", or dashes "-". However, <identifier> cannot begin '
                   'with periods, underscores, or dashes.'))),
        '<file>': And(
            Use(lambda l: l if not six.PY2 else convert_str_list_to_unicode(l)),
            And(lambda f: all(os.path.exists(x) for x in f if x != '-'),
                error='<file> should be a readable file or directory.'),
            And(lambda f: False if f == ['-'] and not args['--remote-name'] else True,
                error='--remote-name must be provided when uploading from stdin.')),
        '--remote-name': Or(None,
            Use(lambda x: x.decode(sys.getfilesystemencoding()) if six.PY2 else x)),
        '--spreadsheet': Or(None, os.path.isfile,
                            error='--spreadsheet should be a readable file.'),
        '--metadata': Or(None, And(Use(get_args_dict), dict),
                         error='--metadata must be formatted as --metadata="key:value"'),
        '--header': Or(None, And(Use(get_args_dict), dict),
                       error='--header must be formatted as --header="key:value"'),
        '--retries': Use(lambda x: int(x[0]) if x else 0),
        '--sleep': Use(lambda l: int(l[0]), error='--sleep value must be an integer.'),
        '--size-hint': Or(Use(lambda l: str(l[0]) if l else None), int, None,
                          error='--size-hint value must be an integer.'),
        '--status-check': bool,
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print('{0}\n{1}'.format(str(exc), printable_usage(__doc__)), file=sys.stderr)
        sys.exit(1)

    # Make sure the collection being uploaded to exists.
    collection_id = args['--metadata'].get('collection')
    if collection_id and not args['--no-collection-check'] and not args['--status-check']:
        if isinstance(collection_id, list):
            collection_id = collection_id[0]
        collection = session.get_item(collection_id)
        if not collection.exists:
            sys.stderr.write(
                'You must upload to a collection that exists. '
                '"{0}" does not exist.\n{1}\n'.format(collection_id,
                                                      printable_usage(__doc__)))
            sys.exit(1)

    # Status check.
    if args['--status-check']:
        if session.s3_is_overloaded():
            print('warning: {0} is over limit, and not accepting requests. '
                  'Expect 503 SlowDown errors.'.format(args['<identifier>']),
                  file=sys.stderr)
            sys.exit(1)
        else:
            print('success: {0} is accepting requests.'.format(args['<identifier>']))
            sys.exit()

    elif args['<identifier>']:
        item = session.get_item(args['<identifier>'])

    # Upload keyword arguments.
    if args['--size-hint']:
        args['--header']['x-archive-size-hint'] = args['--size-hint']
    # Upload with backups turned on by default.
    if not args['--header'].get('x-archive-keep-old-version'):
        args['--header']['x-archive-keep-old-version'] = '1'

    queue_derive = True if args['--no-derive'] is False else False
    verbose = True if args['--quiet'] is False else False

    upload_kwargs = dict(
        metadata=args['--metadata'],
        headers=args['--header'],
        debug=args['--debug'],
        queue_derive=queue_derive,
        verbose=verbose,
        verify=args['--verify'],
        checksum=args['--checksum'],
        retries=args['--retries'],
        retries_sleep=args['--sleep'],
        delete=args['--delete'],
    )

    # Upload files.
    if not args['--spreadsheet']:
        if args['-']:
            local_file = TemporaryFile()
            local_file.write(sys.stdin.read())
            local_file.seek(0)
        else:
            local_file = args['<file>']

        if isinstance(local_file, (list, tuple, set)) and args['--remote-name']:
            local_file = local_file[0]
        if args['--remote-name']:
            files = {args['--remote-name']: local_file}
        else:
            files = local_file

        for _r in _upload_files(item, files, upload_kwargs):
            if args['--debug']:
                break
            if (not _r) or (not _r.ok):
                ERRORS = True

    # Bulk upload using spreadsheet.
    else:
        # Use the same session for each upload request.
        with io.open(args['--spreadsheet'], 'rU', newline='', encoding='utf-8') as csvfp:
            spreadsheet = csv.DictReader(csvfp)
            prev_identifier = None
            for row in spreadsheet:
                upload_kwargs_copy = deepcopy(upload_kwargs)
                local_file = row['file']
                identifier = row['identifier']
                del row['file']
                del row['identifier']
                if (not identifier) and (prev_identifier):
                    identifier = prev_identifier
                item = session.get_item(identifier)
                # TODO: Clean up how indexed metadata items are coerced
                # into metadata.
                md_args = ['{0}:{1}'.format(k.lower(), v) for (k, v) in row.items() if v]
                metadata = get_args_dict(md_args)
                upload_kwargs_copy['metadata'].update(metadata)
                r = _upload_files(item, local_file, upload_kwargs_copy, prev_identifier,
                                  session)
                for _r in r:
                    if args['--debug']:
                        break
                    if (not _r) or (not _r.ok):
                        ERRORS = True
                prev_identifier = identifier

    if ERRORS:
        sys.exit(1)
