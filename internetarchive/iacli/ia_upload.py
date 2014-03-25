"""Upload files to Archive.org via the Internet Archive's S3 like server API.

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage:
    ia upload [--quiet] [--debug] <identifier>
              (<file>... | - --remote-name=<name>)
              [--metadata=<key:value>...] [--header=<key:value>...]
              [--no-derive] [--ignore-bucket] [--size-hint=<size>]
              [--delete] [--log]
    ia upload --help

options:
    -h, --help
    -q, --quiet                    Turn off ia's output [default: False].
    -d, --debug                    Print S3 request parameters to stdout and
                                   exit without sending request.
    -r, --remote-name=<name>       When uploading data from stdin, this option
                                   sets the remote filename.
    -m, --metadata=<key:value>...  Metadata to add to your item.
    -H, --header=<key:value>...    S3 HTTP headers to send with your request.
    -n, --no-derive                Do not derive uploaded files.
    -i, --ignore-bucket            Destroy and respecify all metadata.
    -s, --size-hint=<size>         Specify a size-hint for your item.
    -l, --log                      Log upload results to file.
    --delete                       Delete files after verifying checksums 
                                   [default: False].

"""
import os
import sys
from tempfile import TemporaryFile
from xml.dom.minidom import parseString
from subprocess import call

from docopt import docopt

from internetarchive import get_item
from internetarchive.iacli.argparser import get_args_dict, get_xml_text


# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)
    verbose = True if args['--quiet'] is False else False

    if verbose is not False:
        sys.stdout.write('getting item: {0}\n'.format(args['<identifier>']))

    headers = get_args_dict(args['--header'])
    if args['--size-hint']:
        headers['x-archive-size-hint'] = args['--size-hint']

    upload_kwargs = dict(
        metadata=get_args_dict(args['--metadata']),
        headers=headers,
        debug=args['--debug'],
        queue_derive=True if args['--no-derive'] is False else False,
        ignore_preexisting_bucket=args['--ignore-bucket'],
        verbose=verbose,
        delete=args['--delete'])

    # Upload stdin.
    if args['<file>'] == ['-'] and not args['-']:
        sys.stderr.write('--remote-name is required when uploading from stdin.\n')
        call(['ia', 'upload', '--help'])
        sys.exit(1)
    if args['-']:
        local_file = TemporaryFile()
        local_file.write(sys.stdin.read())
        local_file.seek(0)
        upload_kwargs['key'] = args['--remote-name']
    # Upload files.
    else:
        local_file = args['<file>']

    config = {} if not args['--log'] else {'logging': {'level': 'INFO'}}
    item = get_item(args['<identifier>'], config=config)
    response = item.upload(local_file, **upload_kwargs)

    if args['--debug']:
        for i, r in enumerate(response):
            if i != 0:
                sys.stdout.write('---\n')
            headers = '\n'.join([' {0}: {1}'.format(k, v) for (k, v) in r.headers.items()])
            sys.stdout.write('Endpoint:\n {0}\n\n'.format(r.url))
            sys.stdout.write('HTTP Headers:\n{0}\n'.format(headers))
    else:
        for resp in response:
            if resp.status_code == 200:
                continue
            error = parseString(resp.content)
            code = get_xml_text(error.getElementsByTagName('Code'))
            msg = get_xml_text(error.getElementsByTagName('Message'))
            sys.stderr.write('error "{0}" ({1}): {2}\n'.format(code, resp.status_code, msg))
            sys.exit(1)
