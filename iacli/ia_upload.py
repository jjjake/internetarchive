"""Upload files to Archive.org via the Internet Archive's S3 like server API. 

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage: 
    ia upload [--verbose] [--debug] <identifier> 
              (<file>... | - --remote-name=<name>)
              [--metadata=<key:value>...] [--header=<key:value>...]
              [--no-derive] [--ignore-bucket]
    ia upload --help

options:
    -h, --help
    -v, --verbose                  Print upload status to stdout.
    -d, --debug                    Print S3 request parameters to stdout and 
                                   exit without sending request.
    -r, --remote-name=<name>       When uploading data from stdin, this option 
                                   sets the remote filename.
    -m, --metadata=<key:value>...  Metadata to add to your item.
    -H, --header=<key:value>...    S3 HTTP headers to send with your request.
    -n, --no-derive                Do not derive uploaded files.
    -i, --ignore-bucket            Destroy and respecify all metadata.

"""
import os
from sys import stdin, stdout, stderr, exit
from tempfile import TemporaryFile
from xml.dom.minidom import parseString
from subprocess import call

from docopt import docopt

from internetarchive import upload
from iacli.argparser import get_args_dict, get_xml_text



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    if args['--verbose'] and not args['--debug']:
        stdout.write('getting item: {0}\n'.format(args['<identifier>']))

    upload_kwargs = dict(
            metadata=get_args_dict(args['--metadata']), 
            headers=get_args_dict(args['--header']), 
            debug=args['--debug'], 
            queue_derive=args['--no-derive'], 
            ignore_bucket=args['--ignore-bucket'],
            verbose=args['--verbose'])

    # Upload stdin.
    if args['<file>'] == ['-'] and not args['-']:
        stderr.write('--remote-name is required when uploading from stdin.\n')
        call(['ia', 'upload', '--help'])
        exit(1)
    if args['-']:
        local_file = TemporaryFile()
        local_file.write(stdin.read())
        local_file.seek(0)
        upload_kwargs['remote_name'] = args['--remote-name']
    # Upload files.
    else:
        local_file = args['<file>']

    response = upload(args['<identifier>'], local_file, **upload_kwargs)

    if args['--debug']:
        for i, r in enumerate(response):
            if i != 0:
                stdout.write('---\n')
            headers = '\n'.join([' {0}: {1}'.format(k,v) for (k,v) in r.headers.items()])
            stdout.write('Endpoint:\n {0}\n\n'.format(r.url))
            stdout.write('HTTP Headers:\n{0}\n'.format(headers))
    else:
        for resp in response:
            if resp.status_code == 200:
                continue
            error = parseString(resp.content)
            code = get_xml_text(error.getElementsByTagName('Code'))
            msg = get_xml_text(error.getElementsByTagName('Message'))
            stderr.write('error "{0}" ({1}): {2}\n'.format(code, resp.status_code, msg))
            exit(1)
