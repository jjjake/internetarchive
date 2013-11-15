"""Retrieve and modify metadata for items on archive.org.

usage: 
    ia metadata [--modify=<key:value>... | --exists | --formats ] [--files] [--target=<target>...] <identifier>
    ia metadata --help

options:
    -h, --help
    -m, --modify=<key:value>   Modify the metadata of an item.
    -e, --exists               Check if an item exists.  exists, and 1 if it 
                               does not.
    -f, --files                Return select file-level metadata.
    -F, --formats              Return the file-formats the given item contains.
    -t, --target=<target>...   Return specified target, only.

"""
from sys import stdout, stderr, exit
from json import dumps

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
            stdout.write('{0} exists\n'.format(item.identifier))
            exit(0)
        else:
            stderr.write('{0} does not exist\n'.format(item.identifier))
            exit(1)

    # Modify metadata.
    elif args['--modify']:
        metadata = get_args_dict(args['--modify'])
        response = modify_metadata(args['<identifier>'], metadata)
        status_code = response['status_code']
        if not response['content']['success']:
            error_msg = response['content']['error']
            stderr.write('error: {0} ({1})\n'.format(error_msg, status_code))
            exit(1)
        stdout.write('success: {0}\n'.format(response['content']['log']))

    # Get metadata.
    elif args['--files']:
        for i, f in enumerate(item.files()):
            if not args['--target']:
                files_md = [f.item.identifier, f.name, f.source, f.format, f.size, f.md5]
            else:
                files_md = [f.__dict__.get(k) for k in args['--target']]
            stdout.write('\t'.join([str(x) for x in files_md]) + '\n')
    elif args['--formats']:
        formats = set([f.format for f in item.files()])
        stdout.write('\n'.join(formats) + '\n')
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
        stdout.write('\t'.join([str(x) for x in metadata]) + '\n')
    else:
        metadata = dumps(item.metadata)
        stdout.write(metadata + '\n')
    exit(0)
