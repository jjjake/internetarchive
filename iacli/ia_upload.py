"""Upload files to Archive.org via the Internet Archive's S3 like server API. 

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage: 
    ia upload <identifier> [<file>...|-] [options...]

options:

 -h, --help
 -v, --verbose                  Print upload status to stdout.
 -d, --debug                    Print S3 request parameters to stdout and exit. [default: True]
 -r, --remote-name=<name>       When uploading data from stdin, this option sets the remote filename.
 -m, --metadata=<key:value>...  Metadata to add to your item.
 -H, --header=<key:value>...    Valid S3 HTTP headers to send with your request.
 -n, --no-derive                Do not derive uploaded files.
 -M, --multipart                Upload files to archive.org in parts, using multipart.
 -i, --ignore-bucket            Destroy and respecify all metadata. [default: True]

"""
from sys import stdin, stdout, stderr, exit
from tempfile import TemporaryFile
from xml.dom.minidom import parseString

from docopt import docopt

from internetarchive import upload
from iacli.argparser import get_args_dict



# get_xml_text()
#_________________________________________________________________________________________
def get_xml_text(elements, text=''):
    """:todo: document ``get_xml_text()`` function."""
    for e in elements:
        for node in e.childNodes:
            if node.nodeType == node.TEXT_NODE:
                text += node.data
    return text


# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    if args['--verbose'] and not args['--debug']:
        stdout.write('getting item: {0}\n'.format(args['<identifier>']))

    metadata = get_args_dict(args['--metadata'])
    s3_headers = get_args_dict(args['--header'])

    upload_kwargs = dict(
            metadata=metadata, 
            headers=s3_headers, 
            debug=args['--debug'], 
            queue_derive=args['--no-derive'], 
            ignore_bucket=args['--ignore-bucket'],
            verbose=args['--verbose'],
    )

    if args['<file>'] == ['-']:
        local_file = TemporaryFile()
        local_file.write(stdin.read())
        local_file.seek(0)
        upload_kwargs['remote_name'] = args['--remote-name'][0]
    else:
        local_file = args['<file>']

    response = upload(args['<identifier>'], local_file, **upload_kwargs)

    if args['--debug']:
        for r in response:
            headers = '\n'.join([' {0}: {1}'.format(k,v) for (k,v) in r.headers.items()])
            stdout.write('---\n\nEndpoint:\n {0}\n\n'.format(r.url))
            stdout.write('HTTP Headers:\n{0}\n\n'.format(headers))
    else:
        for resp in response:
            if resp.status_code == 200:
                continue
            error = parseString(resp.content)
            code = get_xml_text(error.getElementsByTagName('Code'))
            msg = get_xml_text(error.getElementsByTagName('Message'))
            stderr.write('error "{0}" ({1}): {2}\n'.format(code, resp.status_code, msg))
            exit(1)
