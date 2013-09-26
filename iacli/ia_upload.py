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
import sys
from collections import defaultdict

from docopt import docopt

from internetarchive import upload



# get_args_dict()
#_________________________________________________________________________________________
def get_args_dict(args):
    metadata = defaultdict(list)
    for md in args:
        key, value = md.split(':')
        metadata[key].append(value)
    # Flatten single item lists.
    for key, value in metadata.items():
        if len(value) <= 1:
            metadata[key] = value[0]
    return metadata


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
        sys.stdout.write('IA-S3 Headers:\n\n{0}\n'.format(headers_str))
        sys.exit(0)
    elif not upload_status:
        sys.stderr.write('error: upload failed!\n')
        sys.exit(1)
    else:
        details_url = 'https://archive.org/details/{0}'.format(args['<identifier>'])
        sys.stdout.write('uploaded:\t{0}\n'.format(details_url))
        sys.exit(0)
