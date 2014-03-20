"""Retrieve and modify metadata for items on archive.org.

usage: 
    ia metadata [--modify=<key:value>...] <identifier>
    ia metadata [--append=<key:value>...] <identifier>
    ia metadata [--exists | --formats] <identifier>
    ia metadata --help

options:
    -h, --help
    -m, --modify=<key:value>   Modify the metadata of an item.
    -a, --append=<key:value>   Append metadata to an element.
    -e, --exists               Check if an item exists.  exists, and 1 if it 
                               does not.
    -F, --formats              Return the file-formats the given item contains.

"""
import sys
from json import dumps

from docopt import docopt

from internetarchive import get_item, modify_metadata
from internetarchive.iacli.argparser import get_args_dict



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)
    item = get_item(args['<identifier>'])

    # Check existence of item.
    if args['--exists']:
        if item.exists:
            sys.stdout.write('{0} exists\n'.format(item.identifier))
            sys.exit(0)
        else:
            sys.stderr.write('{0} does not exist\n'.format(item.identifier))
            sys.exit(1)

    # Modify metadata.
    elif args['--modify'] or args['--append']:
        append = True if args['--append'] else False
        metadata_args = args['--modify'] if args['--modify'] else args['--append']
        metadata = get_args_dict(metadata_args)
        response = modify_metadata(args['<identifier>'], metadata, append=append)
        if not response.json()['success']:
            error_msg = response.json()['error']
            sys.stderr.write('error: {0} ({1})\n'.format(error_msg, response.status_code))
            sys.exit(1)
        sys.stdout.write('success: {0}\n'.format(response.json()['log']))

    # Get metadata.
    elif args['--formats']:
        formats = set([f.format for f in item.iter_files()])
        sys.stdout.write('\n'.join(formats) + '\n')
    else:
        metadata = dumps(item.metadata)
        sys.stdout.write(metadata + '\n')
    sys.exit(0)
