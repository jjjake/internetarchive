"""Retrieve and modify metadata for items on archive.org.

usage: 
    ia metadata [--help] <identifier> [--modify <key:value>... | options...]

options:
    -h, --help
    -m, --modify <key:value>   Modify the metadata of an item.
    -e, --exists               Check if an item exists. Exit status is 0 if the item
                               exists, and 1 if it does not.
    -f, --files                Return select file-level metadata.
    -F, --formats               
    -c, --files-count          Return the file-count of an item.
    -i, --item-size            Return the item-size.
    -s, --server               Return the server from which the given item is being 
                               served.
    --dir                      Return the full item-directory path.
    --d1                       Return the primary server.
    --d2                       Return the secondary server.
    -t, --target <target>      Return specified target, only.

"""
from docopt import docopt
import sys

import internetarchive
from internetarchive import get_item, modify_metadata
from iacli.argparser import get_args_dict



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)
    item = internetarchive.Item(args['<identifier>'])

    # Check existence of item.
    if args['--exists']:
        if item.exists:
            sys.stdout.write('{0} exists\n'.format(item.identifier))
            sys.exit(0)
        else:
            sys.stderr.write('{0} does not exist\n'.format(item.identifier))
            sys.exit(1)

    # Modify metadata.
    elif args['--modify']:
        metadata = get_args_dict(args['--modify'])
        response = modify_metadata(args['<identifier>'], metadata)
        status_code = response['status_code']
        if not response['content']['success']:
            error_msg = response['content']['error']
            sys.stderr.write('error: {0} ({1})\n'.format(error_msg, status_code))
            sys.exit(1)
        sys.stdout.write('success: {0}\n'.format(response['content']['log']))

    # Get metadata.
    elif args['--files']:
        for f in item.files():
            files_md = [f.item.identifier, f.name, f.source, f.format, f.size, f.md5]
            sys.stdout.write('\t'.join([str(x) for x in files_md]) + '\n')
    elif args['--formats']:
        formats = set([f.format for f in item.files()])
        sys.stdout.write('\n'.join(formats))
    elif args['--files-count']:
        sys.stdout.write(str(item.metadata.get('files_count')))
    elif args['--server']:
        sys.stdout.write(str(item.metadata.get('server')))
    elif args['--dir']:
        sys.stdout.write(str(item.metadata.get('dir')))
    elif args['--d1']:
        sys.stdout.write(str(item.metadata.get('d1')))
    elif args['--d2']:
        sys.stdout.write(str(item.metadata.get('d2')))
    elif args['--item-size']:
        sys.stdout.write(str(item.metadata.get('item_size')))
    elif args['--target']:
        keys = [k.strip('/') for k in args['--target'][0].split('/') if k]
        for i, k in enumerate(keys):
            if i == 0:
                md = item.metadata.get(k)
            else:
                md = md.get(k)
        sys.stdout.write(str(md))
    else:
        sys.stdout.write(str(item.metadata))

    sys.exit(0)
