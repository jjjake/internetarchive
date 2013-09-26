"""Upload files to Archive.org via the Internet Archive's S3 like server API. 

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage: 
    ia upload <identifier> <file>... [options...]

options:

 -h, --help
 -d, --debug                    Return the headers to be sent to IA-S3. [default: True]
 -m, --metadata=<key:value>...  Metadata fort your item.
 -H, --header=<key:value>...    Valid S3 HTTP headers to send with your request.
 -n, --no-derive                Do not derive uploaded files.
 -M, --multipart                Upload files to archive.org in parts, using multipart.
 -i, --ignore-bucket            Destroy and respecify all metadata. [default: True]

"""
from sys import stdout, stderr, exit
from collections import defaultdict

from docopt import docopt

from internetarchive import upload
from iacli.argparser import get_args_dict



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    metadata = get_args_dict(args['--metadata'])
    s3_headers = get_args_dict(args['--header'])

    upload_status = upload(args['<identifier>'], 
                           args['<file>'], 
                           metadata=metadata, 
                           headers=s3_headers, 
                           debug=args['--debug'], 
                           derive=args['--no-derive'], 
                           multipart=args['--multipart'],
                           ignore_bucket=args['--ignore-bucket'])

    if args['--debug']:
        headers_str = '\n'.join([': '.join(h) for h in upload_status.items()])
        stdout.write('IA-S3 Headers:\n\n{0}\n'.format(headers_str))
        exit(0)
    elif not upload_status:
        stderr.write('error: upload failed!\n')
        exit(1)
    else:
        details_url = 'https://archive.org/details/{0}'.format(args['<identifier>'])
        stdout.write('uploaded:\t{0}\n'.format(details_url))
        exit(0)
