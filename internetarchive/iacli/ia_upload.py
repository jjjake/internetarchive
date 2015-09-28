"""Upload files to Archive.org via the Internet Archive's S3 like server API.

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage:
    ia upload [--quiet] [--debug]
              (<identifier> <file>... | <identifier> - --remote-name=<name> | <identifier> <file> --remote-name=<name> | --spreadsheet=<metadata.csv>)
              [--metadata=<key:value>...] [--header=<key:value>...] [--checksum]
              [--no-derive] [--ignore-bucket] [--size-hint=<size>]
              [--delete] [--retries=<i>] [--sleep=<i>] [--log] [--no-collection-check]
    ia upload <identifier> --status-check
    ia upload --help

options:
    -h, --help
    -q, --quiet                       Turn off ia's output [default: False].
    -d, --debug                       Print S3 request parameters to stdout and
                                      exit without sending request.
    -r, --remote-name=<name>          When uploading data from stdin, this option
                                      sets the remote filename.
    -S, --spreadsheet=<metadata.csv>  bulk uploading...
    -m, --metadata=<key:value>...     Metadata to add to your item.
    -H, --header=<key:value>...       S3 HTTP headers to send with your request.
    -c, --checksum                    Skip based on checksum [default: False].
    -n, --no-derive                   Do not derive uploaded files.
    -i, --ignore-bucket               Destroy and respecify all metadata.
    -s, --size-hint=<size>            Specify a size-hint for your item.
    -R, --retries=<i>                 Number of times to retry request if S3
                                      retruns a 503 SlowDown error.
    -s, --sleep=<i>                   The amount of time to sleep between retries
                                      [default: 30].
    -l, --log                         Log upload results to file.
    --status-check                    Check if S3 is accepting requests to the
                                      given item.
    --delete                          Delete files after verifying checksums 
                                      [default: False].
    --no-collection-check             Skip checking if the collection being
                                      uploaded to exists [default: False].

"""
import sys
from tempfile import TemporaryFile
from xml.dom.minidom import parseString
from subprocess import call
import csv

from docopt import docopt, printable_usage
from requests.exceptions import HTTPError
import six

from internetarchive.session import ArchiveSession
from internetarchive import get_item
from internetarchive.iacli.argparser import get_args_dict, get_xml_text


# _upload_files()
# ________________________________________________________________________________________
def _upload_files(args, identifier, local_file, upload_kwargs, prev_identifier=None,
                  archive_session=None):
    verbose = True if args['--quiet'] is False else False
    config = {} if not args['--log'] else {'logging': {'level': 'INFO'}}
    item = get_item(identifier, config=config)
    if args['--status-check']:
        if item.s3_is_overloaded():
            sys.stderr.write('warning: {0} is over limit, and not accepting requests. '
                             'Expect 503 SlowDown errors.\n'.format(identifier))
            sys.exit(1)
        else:
            sys.stdout.write('success: {0} is accepting requests.\n'.format(identifier))
            sys.exit(0)
    if (verbose) and (prev_identifier != identifier):
        sys.stdout.write('{0}:\n'.format(item.identifier))

    try:
        if isinstance(local_file, (list, tuple, set)) and args['--remote-name']:
            local_file = local_file[0]
        if args['--remote-name']:
            files = {args['--remote-name']: local_file}
        else:
            files = local_file
        response = item.upload(files, **upload_kwargs)
    except HTTPError as exc:
        response = [exc.response]
        if not response[0]:
            sys.exit(1)
        if response[0].status_code == 403:
            if (not item.session.access_key) and (not item.session.secret_key):
                sys.stderr.write('\nIAS3 Authentication failed. Please set your IAS3 '
                                 'access key and secret key \nvia the environment '
                                 'variables `IAS3_ACCESS_KEY` and `IAS3_SECRET_KEY`, '
                                 'or \nrun `ia configure` to add your IAS3 keys to your '
                                 'ia config file. You can \nobtain your IAS3 keys at the '
                                 'following URL:\n\n\t'
                                 'https://archive.org/account/s3.php\n\n')
            else:
                sys.stderr.write('\nIAS3 Authentication failed. It appears the keyset '
                                 '"{0}:{1}" \ndoes not have permission to upload '
                                 'to the given item or '
                                 'collection.\n\n'.format(item.session.access_key,
                                                          item.session.secret_key))
            sys.exit(1)

    if args['--debug']:
        for i, r in enumerate(response):
            if i != 0:
                sys.stdout.write('---\n')
            headers = '\n'.join(
                [' {0}: {1}'.format(k, v) for (k, v) in r.headers.items()]
            )
            sys.stdout.write('Endpoint:\n {0}\n\n'.format(r.url))
            sys.stdout.write('HTTP Headers:\n{0}\n'.format(headers))

    else:
        for resp in response:
            if not resp:
                continue
            if (resp.status_code == 200) or (not resp.status_code):
                continue
            error = parseString(resp.content)
            code = get_xml_text(error.getElementsByTagName('Code'))
            msg = get_xml_text(error.getElementsByTagName('Message'))
            sys.stderr.write(
                'error "{0}" ({1}): {2}\n'.format(code, resp.status_code, msg)
            )
            sys.exit(1)


# main()
# ________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    metadata = get_args_dict(args['--metadata'])
    # Make sure the collection being uploaded to exists.
    collection_ids = metadata.get('collection', [])
    if isinstance(collection_ids, six.string_types):
        collection_ids = [collection_ids]
    for cid in collection_ids:
        if args['--no-collection-check'] or args['--status-check']:
            break
        collection = get_item(cid) 
        if not collection.exists:
            sys.stderr.write(
                    'You must upload to a collection that exists. '
                    '"{0}" does not exist.\n{1}\n'.format(collection.identifier,
                                                          printable_usage(__doc__)))
            sys.exit(1)

    headers = get_args_dict(args['--header'])
    if args['--size-hint']:
        headers['x-archive-size-hint'] = args['--size-hint']

    # Upload keyword arguments.
    upload_kwargs = dict(
        metadata=metadata,
        headers=headers,
        debug=args['--debug'],
        queue_derive=True if args['--no-derive'] is False else False,
        ignore_preexisting_bucket=args['--ignore-bucket'],
        checksum=args['--checksum'],
        verbose=True if args['--quiet'] is False else False,
        retries=int(args['--retries']) if args['--retries'] else 0,
        retries_sleep=int(args['--sleep']),
        delete=args['--delete'],
    )

    if args['<file>'] == ['-'] and not args['-']:
        sys.stderr.write('--remote-name is required when uploading from stdin.\n')
        call(['ia', 'upload', '--help'])
        sys.exit(1)

    # Upload from stdin.
    if args['-']:
        local_file = TemporaryFile()
        local_file.write(sys.stdin.read())
        local_file.seek(0)
        _upload_files(args, args['<identifier>'], local_file, upload_kwargs)

    # Bulk upload using spreadsheet.
    elif args['--spreadsheet']:
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
            # TODO: Clean up how indexed metadata items are coerced
            # into metadata.
            md_args = ['{0}:{1}'.format(k.lower(), v) for (k, v) in row.items() if v]
            metadata = get_args_dict(md_args)
            upload_kwargs['metadata'].update(metadata)
            _upload_files(args, identifier, local_file, upload_kwargs, prev_identifier,
                          session)
            prev_identifier = identifier

    # Upload files.
    else:
        local_file = args['<file>']
        _upload_files(args, args['<identifier>'], local_file, upload_kwargs)
