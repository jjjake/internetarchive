"""Upload items to archive.org.

usage: 
    ia upload <identifier> <file>... [options...]

options:

 -h, --help
 -n, --no-derive             Do not derive the item after files have been 
                             uploaded.
 -d, --debug                 Return the headers to be sent to IA-S3. default: True
 -M, --multipart             Upload files to archive.org in parts, using 
                             IA-S3 multipart.
 -i, --ignore-bucket         Destroy and respecify the metadata for a 
                             given item.
 -m, --metadata=<key:value>  Metadata to add to the item. default: None
 -H, --header=<key:value>    default: None

"""
from docopt import docopt
import sys

import internetarchive



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    s3_headers = dict(h.split(':') for h in args['--header'] if args['--header'])
    s3_metadata = {}
    changes = [x.split(':', 1) for x in args['--metadata']]
    for k,v in changes:
        if not s3_metadata.get(k):
            s3_metadata[k] = v
        else:
            if type(s3_metadata[k]) != list:
                s3_metadata[k] = [s3_metadata[k]]
            s3_metadata[k].append(v)

    item = internetarchive.Item(args['<identifier>'])
    upload_status = item.upload(args['<file>'], metadata=s3_metadata, headers=s3_headers,
                                debug=args['--debug'], derive=args['--no-derive'], 
                                multipart=args['--multipart'],
                                ignore_bucket=args['--ignore-bucket'])
    if args['--debug']:
        sys.stdout.write('IA-S3 Headers:\n\n{0}\n'.format(upload_status))
        sys.exit(0)
    elif not upload_status:
        sys.stderr.write('error: upload failed!\n')
        sys.exit(1)
    else:
        sys.stdout.write('uploaded:\t{0}\n'.format(item.details_url))
        sys.exit(0)
