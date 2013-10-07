"""Upload files to Archive.org via the Internet Archive's S3 like server API. 

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage: 
    ia upload <identifier> [<file>...|-] [options...]

options:

 -h, --help
 -d, --debug                    Return the headers to be sent to IA-S3. [default: True]
 -r, --remote-name=<name>       When uploading data from stdin, this option sets the
                                remote filename.
 -m, --metadata=<key:value>...  Metadata fort your item.
 -H, --header=<key:value>...    Valid S3 HTTP headers to send with your request.
 -n, --no-derive                Do not derive uploaded files.
 -M, --multipart                Upload files to archive.org in parts, using multipart.
 -i, --ignore-bucket            Destroy and respecify all metadata. [default: True]

"""
from sys import stdin, stdout, stderr, exit
from collections import defaultdict
from tempfile import TemporaryFile
from xml.dom.minidom import parseString

from docopt import docopt

from internetarchive import upload, upload_file
from iacli.argparser import get_args_dict



# get_xml_text()
#_________________________________________________________________________________________
def get_xml_text(elements, text=''):
    for e in elements:
        for node in e.childNodes:
            if node.nodeType == node.TEXT_NODE:
                text += node.data
    return text


# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    metadata = get_args_dict(args['--metadata'])
    s3_headers = get_args_dict(args['--header'])

    upload_kwargs = dict(
            metadata=metadata, 
            headers=s3_headers, 
            debug=args['--debug'], 
            queue_derive=args['--no-derive'], 
            ignore_bucket=args['--ignore-bucket'])

    if args['<file>'] == ['-']:
        local_file = TemporaryFile()
        local_file.write(stdin.read())
        local_file.seek(0)
        upload_kwargs['remote_name'] = args['--remote-name'][0]
    else:
        local_file = args['<file>']
    response = upload(args['<identifier>'], local_file, **upload_kwargs)


    if args['--debug']:
        headers_str = '\n'.join([': '.join(h) for h in response.items()])
        stdout.write('IA-S3 Headers:\n\n{0}\n'.format(headers_str))
        exit(0)
    else:
        for resp in response:
            if resp.status_code == 200:
                continue
            error = parseString(resp.content)
            code = get_xml_text(error.getElementsByTagName('Code'))
            msg = get_xml_text(error.getElementsByTagName('Message'))
            stderr.write('error "{0}" ({1}): {2}\n'.format(code, resp.status_code, msg))
            exit(1)

    details_url = 'https://archive.org/details/{0}'.format(args['<identifier>'])
    stdout.write('uploaded:\t{0}\n'.format(details_url))
    exit(0)
