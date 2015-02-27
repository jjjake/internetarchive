"""Upload files to Archive.org via the Internet Archive's S3 like server API.

IA-S3 Documentation: https://archive.org/help/abouts3.txt

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
    -n, --no-derive                   Do not derive uploaded files.
    -i, --ignore-bucket               Destroy and respecify all metadata.
    --size-hint=<size>                Specify a size-hint for your item.
    --delete                          Delete files after verifying checksums
                                      [default: False].
    -R, --retries=<i>                 Number of times to retry request if S3 retruns a
                                      503 SlowDown error.
    -s, --sleep=<i>                   The amount of time to sleep between retries
                                      [default: 30].
    -l, --log                         Log upload results to file.
    --status-check                    Check if S3 is accepting requests to the given item.

"""
import sys
import os
from tempfile import TemporaryFile
from xml.dom.minidom import parseString
import csv

from docopt import docopt, printable_usage
from requests.exceptions import HTTPError
from schema import Schema, Use, Or, And, SchemaError

from internetarchive.session import ArchiveSession
from internetarchive import get_item
from internetarchive.cli.argparser import get_args_dict, get_xml_text
from internetarchive.utils import validate_ia_identifier


# _upload_files()
# ________________________________________________________________________________________
def _upload_files(item, files, upload_kwargs, prev_identifier=None, archive_session=None):
    """Helper function for calling :meth:`Item.upload`"""
    if (upload_kwargs['verbose']) and (prev_identifier != item.identifier):
        sys.stdout.write('{0}:\n'.format(item.identifier))

    try:
        response = item.upload(files, **upload_kwargs)
    except HTTPError as exc:
        response = [exc.response]
    finally:
        # Debug mode.
        if upload_kwargs['debug']:
            for i, r in enumerate(response):
                if i != 0:
                    sys.stdout.write('---\n')
                headers = '\n'.join(
                    [' {0}: {1}'.format(k, v) for (k, v) in r.headers.items()]
                )
                sys.stdout.write('Endpoint:\n {0}\n\n'.format(r.url))
                sys.stdout.write('HTTP Headers:\n{0}\n'.format(headers))
                sys.exit(0)

        # Missing S3 keys.
        if response[0].status_code == 403:
            if (not item.session.access_key) or (not item.session.secret_key):
                sys.stderr.write('\nIAS3 Authentication failed. Please set your IAS3 '
                                 'access key and secret key \nvia the environment '
                                 'variables `IAS3_ACCESS_KEY` and `IAS3_SECRET_KEY`, '
                                 'or \nrun `ia configure` to add your IAS3 keys to your '
                                 'ia config file. You can \nobtain your IAS3 keys at the '
                                 'following URL:\n\n\t'
                                 'https://archive.org/account/s3.php\n\n')
                sys.exit(1)

        # Format error message for any non 200 responses that
        # we haven't caught yet,and write to stderr.
        if response[0].status_code != 200:
            filename = response[0].request.url.split('/')[-1]
            error = parseString(response[0].content)
            msg = get_xml_text(error.getElementsByTagName('Message'))
            sys.stderr.write(
                ' * error uploading {0} ({1}): {2}\n'.format(filename,
                    response[0].status_code, msg)
            )
            sys.exit(1)


# main()
# ________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    # Validate args.
    s = Schema({str: Use(bool),
        '<identifier>': Or(None, And(str, validate_ia_identifier,
            error=('<identifier> should be between 3 and 80 characters in length, and '
                   'can only contain alphanumeric characters, underscores ( _ ), or '
                   'dashes ( - )'))),
        '<file>': And(
            And(lambda f: all(os.path.exists(x) for x in f if x != '-'),
                error='<file> should be a readable file or directory.'),
            And(lambda f: False if f == ['-'] and not args['--remote-name'] else True,
                error='--remote-name must be provided when uploading from stdin.')),
        '--remote-name': Or(None, And(str)),
        '--spreadsheet': Or(None, os.path.isfile,
            error='--spreadsheet should be a readable file.'),
        '--metadata': Or(None, And(Use(get_args_dict), dict),
            error='--metadata must be formatted as --metadata="key:value"'),
        '--header': Or(None, And(Use(get_args_dict), dict),
            error='--header must be formatted as --header="key:value"'),
        '--retries': Use(lambda x: int(x[0]) if x else 0),
        '--sleep': Use(lambda l: int(l[0]), error='--sleep value must be an integer.'),
        '--size-hint': Or(Use(lambda l: int(l[0]) if l else None), int, None,
            error='--size-hint value must be an integer.'),
        '--status-check': bool,
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        sys.exit(sys.stderr.write('{0}\n{1}\n'.format(
            str(exc), printable_usage(__doc__))))

    # Load Item.
    config = {} if not args['--log'] else {'logging': {'level': 'INFO'}}
    item = get_item(args['<identifier>'], config=config) if args['<identifier>'] else None

    # Status check.
    if args['--status-check']:
        if item.s3_is_overloaded():
            sys.exit(sys.stderr.write(
                'warning: {0} is over limit, and not accepting requests. '
                'Expect 503 SlowDown errors.\n'.format(args['<identifier>'])))
        else:
            sys.exit(sys.stdout.write(
                'success: {0} is accepting requests.\n'.format(args['<identifier>'])))

    # Upload keyword arguments.
    if args['--size-hint']:
        args['--header']['x-archive-size-hint'] = args['--size-hint']

    queue_derive = True if args['--no-derive'] is False else False
    verbose = True if args['--quiet'] is False else False

    upload_kwargs = dict(
        metadata=args['--metadata'],
        headers=args['--header'],
        debug=args['--debug'],
        queue_derive=queue_derive,
        ignore_preexisting_bucket=args['--ignore-bucket'],
        checksum=args['--checksum'],
        verbose=verbose,
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

        _upload_files(item, files, upload_kwargs)

    # Bulk upload using spreadsheet.
    else:
        # Use the same session for each upload request.
        session = ArchiveSession()
        spreadsheet = csv.DictReader(open(args['--spreadsheet'], 'rU'))
        prev_identifier = None
        for row in spreadsheet:
            local_file = row['file']
            identifier = row['identifier']
            del row['file']
            del row['identifier']
            if (not identifier) and (prev_identifier):
                identifier = prev_identifier
            item = get_item(identifier, config=config)
            # TODO: Clean up how indexed metadata items are coerced
            # into metadata.
            md_args = ['{0}:{1}'.format(k.lower(), v) for (k, v) in row.items() if v]
            metadata = get_args_dict(md_args)
            upload_kwargs['metadata'].update(metadata)
            _upload_files(item, local_file, upload_kwargs, prev_identifier, session)
            prev_identifier = identifier
