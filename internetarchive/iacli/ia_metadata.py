"""Retrieve and modify metadata for items on archive.org.

usage:
    ia metadata [--modify=<key:value>...] [--target=<target>] [--priority=<priority>] <identifier>...
    ia metadata [--spreadsheet=<metadata.csv>] [--priority=<priority>] [--modify=<key:value>...]
    ia metadata [--append=<key:value>...] [--priority=<priority>] <identifier>...
    ia metadata [--exists | --formats] <identifier>...
    ia metadata --help

options:
    -h, --help
    -m, --modify=<key:value>          Modify the metadata of an item.
    -t, --target=<target>             The metadata target to modify.
    -a, --append=<key:value>          Append metadata to an element.
    -s, --spreadsheet=<metadata.csv>  Modify metadata in bulk using a spreadsheet as input.
    -e, --exists                      Check if an item exists
    -F, --formats                     Return the file-formats the given item contains.
    -p, --priority=<priority>        Set the task priority.

"""
import sys
try:
    import ujson as json
except ImportError:
    import json
import csv

from docopt import docopt

from internetarchive import get_item
from internetarchive.iacli.argparser import get_args_dict


# modify_metadata()
# ________________________________________________________________________________________
def modify_metadata(item, metadata, args):
    append = True if args['--append'] else False
    r = item.modify_metadata(metadata, target=args['--target'], append=append,
                             priority=args['--priority'])
    if not r.json()['success']:
        error_msg = r.json()['error']
        sys.stderr.write(u'{0} - error ({1}): {2}\n'.format(item.identifier, r.status_code,
                                                           error_msg))
        return r
    sys.stdout.write('{0} - success: {1}\n'.format(item.identifier,
                                                   r.json()['log']))
    return r


# main()
# ________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    formats = set()
    responses = []

    for i, _item in enumerate(args['<identifier>']):
        item = get_item(_item)

        # Check existence of item.
        if args['--exists']:
            if item.exists:
                responses.append(True)
                sys.stdout.write('{0} exists\n'.format(item.identifier))
            else:
                responses.append(False)
                sys.stderr.write('{0} does not exist\n'.format(item.identifier))
            if (i + 1) == len(args['<identifier>']):
                if all(r is True for r in responses):
                    sys.exit(0)
                else:
                    sys.exit(1)

        # Modify metadata.
        elif args['--modify'] or args['--append']:
            metadata_args = args['--modify'] if args['--modify'] else args['--append']
            metadata = get_args_dict(metadata_args)
            responses.append(modify_metadata(item, metadata, args))
            if (i + 1) == len(args['<identifier>']):
                if all(r.status_code == 200 for r in responses):
                    sys.exit(0)
                else:
                    sys.exit(1)

        # Get metadata.
        elif args['--formats']:
            for f in item.iter_files():
                formats.add(f.format)
            if (i + 1) == len(args['<identifier>']):
                sys.stdout.write('\n'.join(formats) + '\n')

        # Dump JSON to stdout.
        else:
            metadata = json.dumps(item._json)
            sys.stdout.write(metadata + '\n')

    # Edit metadata for items in bulk, using a spreadsheet as input.
    if args['--spreadsheet']:
        if not args['--priority']:
            args['--priority'] = -5
        spreadsheet = csv.DictReader(open(args['--spreadsheet'], 'rU'))
        responses = []
        for row in spreadsheet:
            if not row['identifier']:
                continue
            item = get_item(row['identifier'])
            if row.get('file'):
                del row['file']
            metadata = dict((k.lower(), v) for (k, v) in row.items() if v)
            responses.append(modify_metadata(item, metadata, args))

        if all(r.status_code == 200 for r in responses):
            sys.exit(0)
        else:
            sys.exit(1)

    sys.exit(0)
