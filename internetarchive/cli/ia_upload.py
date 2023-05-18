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

"""Upload files to Archive.org.

usage:
    ia upload <identifier> <file>... [options]...
    ia upload <identifier> - --remote-name=<name> [options]...
    ia upload <identifier> <file> --remote-name=<name> [options]...
    ia upload --spreadsheet=<metadata.csv> [options]...
    ia upload <identifier> --file-metadata=<file_md.jsonl> [options]...
    ia upload <identifier> --status-check
    ia upload --help

options:
    -h, --help
    -q, --quiet                          Turn off ia's output [default: False].
    -d, --debug                          Print S3 request parameters to stdout and exit
                                         without sending request.
    -r, --remote-name=<name>             When uploading data from stdin, this option sets
                                         the remote filename.
    -S, --spreadsheet=<metadata.csv>     Bulk uploading.
    -f, --file-metadata=<file_md.jsonl>  Upload files with file-level metadata via a
                                         file_md.jsonl file.
    -m, --metadata=<key:value>...        Metadata to add to your item.
    -H, --header=<key:value>...          S3 HTTP headers to send with your request.
    -c, --checksum                       Skip based on checksum. [default: False]
    -v, --verify                         Verify that data was not corrupted traversing the
                                         network. [default: False]
    -n, --no-derive                      Do not derive uploaded files.
    --size-hint=<size>                   Specify a size-hint for your item.
    --delete                             Delete files after verifying checksums
                                         [default: False].
    -R, --retries=<i>                    Number of times to retry request if S3 returns a
                                         503 SlowDown error.
    -s, --sleep=<i>                      The amount of time to sleep between retries
                                         [default: 30].
    --status-check                       Check if S3 is accepting requests to the given
                                         item.
    --no-collection-check                Skip collection exists check [default: False].
    -o, --open-after-upload              Open the details page for an item after upload
                                         [default: False].
    --no-backup                          Turn off archive.org backups. Clobbered files
                                         will not be saved to history/files/$key.~N~
                                         [default: True].
    --keep-directories                   Keep directories in the supplied file paths for
                                         the remote filename. [default: False]
    --no-scanner                         Do not set the scanner field in meta.xml.
"""
import csv
import os
import sys
import webbrowser
from copy import deepcopy
from locale import getpreferredencoding
from pathlib import Path
from tempfile import TemporaryFile

from docopt import docopt, printable_usage
from requests.exceptions import HTTPError
from schema import And, Or, Schema, SchemaError, Use  # type: ignore[import]

from internetarchive.cli.argparser import convert_str_list_to_unicode, get_args_dict
from internetarchive.session import ArchiveSession
from internetarchive.utils import (
    InvalidIdentifierException,
    JSONDecodeError,
    get_s3_xml_text,
    is_valid_metadata_key,
    json,
    validate_s3_identifier,
)


def _upload_files(item, files, upload_kwargs, prev_identifier=None, archive_session=None):
    """Helper function for calling :meth:`Item.upload`"""
    # Check if the list has any element.
    if not files:
        raise FileNotFoundError("No valid file was found. Check your paths.")

    responses = []
    if (upload_kwargs['verbose']) and (prev_identifier != item.identifier):
        print(f'{item.identifier}:', file=sys.stderr)

    try:
        response = item.upload(files, **upload_kwargs)
        responses += response
    except HTTPError as exc:
        responses += [exc.response]
    except InvalidIdentifierException as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        # Debug mode.
        if upload_kwargs['debug']:
            for i, r in enumerate(responses):
                if i != 0:
                    print('---', file=sys.stderr)
                headers = '\n'.join(
                    [f' {k}:{v}' for (k, v) in r.headers.items()]
                )
                print(f'Endpoint:\n {r.url}\n', file=sys.stderr)
                print(f'HTTP Headers:\n{headers}', file=sys.stderr)

    return responses


def main(argv, session):  # noqa: C901
    args = docopt(__doc__, argv=argv)
    ERRORS = False

    # Validate args.
    s = Schema({
        str: Use(bool),
        '<identifier>': Or(None, And(str, validate_s3_identifier,
            error=('<identifier> should be between 3 and 80 characters in length, and '
                   'can only contain alphanumeric characters, periods ".", '
                   'underscores "_", or dashes "-". However, <identifier> cannot begin '
                   'with periods, underscores, or dashes.'))),
        '<file>': And(
            And(lambda f: all(os.path.exists(x) for x in f if x != '-'),
                error='<file> should be a readable file or directory.'),
            And(lambda f: False if f == ['-'] and not args['--remote-name'] else True,
                error='--remote-name must be provided when uploading from stdin.')),
        '--remote-name': Or(None, str),
        '--spreadsheet': Or(None, os.path.isfile,
                            error='--spreadsheet should be a readable file.'),
        '--file-metadata': Or(None, os.path.isfile,
                              error='--file-metadata should be a readable file.'),
        '--metadata': Or(None, And(Use(get_args_dict), dict),
                         error='--metadata must be formatted as --metadata="key:value"'),
        '--header': Or(None, And(Use(get_args_dict), dict),
                       error='--header must be formatted as --header="key:value"'),
        '--retries': Use(lambda x: int(x[0]) if x else 0),
        '--sleep': Use(lambda lst: int(lst[0]), error='--sleep value must be an integer.'),
        '--size-hint': Or(Use(lambda lst: str(lst[0]) if lst else None), int, None,
                          error='--size-hint value must be an integer.'),
        '--status-check': bool,
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print(f'{exc}\n{printable_usage(__doc__)}', file=sys.stderr)
        sys.exit(1)

    # Make sure the collection being uploaded to exists.
    collection_id = args['--metadata'].get('collection')
    if collection_id and not args['--no-collection-check'] and not args['--status-check']:
        if isinstance(collection_id, list):
            collection_id = collection_id[0]
        collection = session.get_item(collection_id)
        if not collection.exists:
            print('You must upload to a collection that exists. '
                  f'"{collection_id}" does not exist.\n{printable_usage(__doc__)}',
                  file=sys.stderr)
            sys.exit(1)

    # Status check.
    if args['--status-check']:
        if session.s3_is_overloaded():
            print(f'warning: {args["<identifier>"]} is over limit, and not accepting requests. '
                  'Expect 503 SlowDown errors.',
                  file=sys.stderr)
            sys.exit(1)
        else:
            print(f'success: {args["<identifier>"]} is accepting requests.', file=sys.stderr)
            sys.exit()

    elif args['<identifier>']:
        item = session.get_item(args['<identifier>'])

    # Upload keyword arguments.
    if args['--size-hint']:
        args['--header']['x-archive-size-hint'] = args['--size-hint']
    # Upload with backups turned on by default.
    if not args['--header'].get('x-archive-keep-old-version') and not args['--no-backup']:
        args['--header']['x-archive-keep-old-version'] = '1'

    queue_derive = True if args['--no-derive'] is False else False
    verbose = True if args['--quiet'] is False else False
    set_scanner = False if args['--no-scanner'] is True else True

    if args['--file-metadata']:
        try:
            with open(args['--file-metadata']) as fh:
                args['<file>'] = json.load(fh)
        except JSONDecodeError:
            args['<file>'] = []
            with open(args['--file-metadata']) as fh:
                for line in fh:
                    j = json.loads(line.strip())
                    args['<file>'].append(j)
    upload_kwargs = {
        'metadata': args['--metadata'],
        'headers': args['--header'],
        'debug': args['--debug'],
        'queue_derive': queue_derive,
        'set_scanner': set_scanner,
        'verbose': verbose,
        'verify': args['--verify'],
        'checksum': args['--checksum'],
        'retries': args['--retries'],
        'retries_sleep': args['--sleep'],
        'delete': args['--delete'],
        'validate_identifier': True,
    }

    # Upload files.
    if not args['--spreadsheet']:
        if args['-']:
            local_file = TemporaryFile()
            # sys.stdin normally has the buffer attribute which returns bytes.
            # However, this might not always be the case, e.g. on mocking for test purposes.
            # Fall back to reading as str and encoding back to bytes.
            # Note that the encoding attribute might also be None. In that case, fall back to
            # locale.getpreferredencoding, the default of io.TextIOWrapper and open().
            if hasattr(sys.stdin, 'buffer'):
                def read():
                    return sys.stdin.buffer.read(1048576)
            else:
                encoding = sys.stdin.encoding or getpreferredencoding(False)

                def read():
                    return sys.stdin.read(1048576).encode(encoding)
            while True:
                data = read()
                if not data:
                    break
                local_file.write(data)
            local_file.seek(0)
        else:
            local_file = args['<file>']
            # Properly expand a period to the contents of the current working directory.
            if '.' in local_file:
                local_file = [p for p in local_file if p != '.']
                local_file = os.listdir('.') + local_file

        if isinstance(local_file, (list, tuple, set)) and args['--remote-name']:
            local_file = local_file[0]
        if args['--remote-name']:
            files = {args['--remote-name']: local_file}
        elif args['--keep-directories']:
            files = {f: f for f in local_file}
        else:
            files = local_file

        for _r in _upload_files(item, files, upload_kwargs):
            if args['--debug']:
                break
            if (not _r.status_code) or (not _r.ok):
                ERRORS = True
            else:
                if args['--open-after-upload']:
                    url = f'{session.protocol}//{session.host}/details/{item.identifier}'
                    webbrowser.open_new_tab(url)

    # Bulk upload using spreadsheet.
    else:
        # Use the same session for each upload request.
        with open(args['--spreadsheet'], newline='', encoding='utf-8-sig') as csvfp:
            spreadsheet = csv.DictReader(csvfp)
            prev_identifier = None
            for row in spreadsheet:
                for metadata_key in row:
                    if not is_valid_metadata_key(metadata_key):
                        print(f'error: "{metadata_key}" is not a valid metadata key.',
                              file=sys.stderr)
                        sys.exit(1)
                upload_kwargs_copy = deepcopy(upload_kwargs)
                if row.get('REMOTE_NAME'):
                    local_file = {row['REMOTE_NAME']: row['file']}
                    del row['REMOTE_NAME']
                elif args['--keep-directories']:
                    local_file = {row['file']: row['file']}
                else:
                    local_file = row['file']
                identifier = row.get('item', row.get('identifier'))
                if not identifier:
                    if not prev_identifier:
                        print('error: no identifier column on spreadsheet.',
                              file=sys.stderr)
                        sys.exit(1)
                    identifier = prev_identifier
                del row['file']
                if 'identifier' in row:
                    del row['identifier']
                if 'item' in row:
                    del row['item']
                item = session.get_item(identifier)
                # TODO: Clean up how indexed metadata items are coerced
                # into metadata.
                md_args = [f'{k.lower()}:{v}' for (k, v) in row.items() if v]
                metadata = get_args_dict(md_args)
                upload_kwargs_copy['metadata'].update(metadata)
                r = _upload_files(item, local_file, upload_kwargs_copy, prev_identifier,
                                  session)
                for _r in r:
                    if args['--debug']:
                        break
                    if (not _r.status_code) or (not _r.ok):
                        ERRORS = True
                    else:
                        if args['--open-after-upload']:
                            url = f'{session.protocol}//{session.host}/details/{identifier}'
                            webbrowser.open_new_tab(url)
                prev_identifier = identifier

    if ERRORS:
        sys.exit(1)
