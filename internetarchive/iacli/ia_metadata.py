"""Retrieve and modify metadata for items on archive.org.

usage: 
    ia metadata [--modify=<key:value>... ] [--target=<target>] <identifier>
    ia metadata [--append=<key:value>... ] [--target=<target>] <identifier>
    ia metadata [--exists | --formats | --files | --target=<target>...] <identifier>
    ia metadata --help

options:
    -h, --help
    -m, --modify=<key:value>   Modify the metadata of an item.
    -a, --append=<key:value>   Append metadata to an element.
    -e, --exists               Check if an item exists.  exists, and 1 if it 
                               does not.
    -f, --files                Return select file-level metadata.
    -F, --formats              Return the file-formats the given item contains.
    -t, --target=<target>...   Return specified target, only.

"""
import sys
import json

from docopt import docopt

from internetarchive import get_item, modify_metadata
from iacli.argparser import get_args_dict



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
        try:
            md = get_args_dict(metadata_args)
        except ValueError:
            sys.stderr.write('error: -m, --modify args must be a key/value pair!\n\n')
            sys.stderr.write(__doc__)
            sys.exit(1)
        response = modify_metadata(args['<identifier>'], metadata, append=append)
        status_code = response['status_code']
        if not response['content']['success']:
            error_msg = response['content']['error']
            sys.stderr.write('error: {0} ({1})\n'.format(error_msg, status_code))
            sys.exit(1)
        sys.stdout.write('success: {0}\n'.format(response['content']['log']))

    # Get metadata.
    elif args['--files']:
        for i, f in enumerate(item.files()):
            if not args['--target']:
                files_md = [f.identifier, f.name, f.source, f.format, f.size, f.md5]
            else:
                files_md = [f.__dict__.get(k) for k in args['--target']]
            sys.stdout.write('\t'.join([str(x) for x in files_md]) + '\n')
    elif args['--formats']:
        formats = set([f.format for f in item.files()])
        sys.stdout.write('\n'.join(formats) + '\n')
    elif args['--target']:
        metadata = []
        for key in args['--target']:
            if '/' in key:
                for i, k in enumerate(key.split('/')):
                    if i == 0:
                        md = item.metadata.get(k)
                    else:
                        if md:    
                            md = md.get(k)
            else:
                md = item.metadata.get(key)
            if md:
                metadata.append(md)
        sys.stdout.write('\t'.join([str(x) for x in metadata]) + '\n')
    else:
        metadata = json.dumps(item.metadata)
        sys.stdout.write(metadata + '\n')
    sys.exit(0)
