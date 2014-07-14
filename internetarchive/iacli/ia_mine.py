"""Concurrently download metadata for items on Archive.org.

usage:
    ia mine [--cache | --output=<output.json>] [--workers=<count>] <itemlist.txt>
    ia mine --help

options:
    -h, --help
    -c, --cache                 Write item metadata to a file called <identifier>_meta.json
    -o, --output=<output.json>  Write all metadata to a single output file <itemlist>.json
    -w, --workers=<count>       The number of requests to run concurrently [default: 20]

"""
import sys
import json

from docopt import docopt

from internetarchive import get_data_miner


# ia_mine()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    if args['<itemlist.txt>'] == '-':
        itemfile = sys.stdin
    else:
        itemfile = open(args['<itemlist.txt>'])
    with itemfile:
        identifiers = [i.strip() for i in itemfile]

    workers = int(args.get('--workers', 20)[0])
    miner = get_data_miner(identifiers, workers=workers)

    for i, item in miner:
        metadata = json.dumps(item._json)
        if args['--cache']:
            sys.stderr.write('saving metadata for: {0}\n'.format(item.identifier))
            with open('{0}_meta.json'.format(item.identifier), 'w') as fp:
                fp.write(metadata)
        elif args['--output']:
            sys.stderr.write('saving metadata for: {0}\n'.format(item.identifier))
            with open(args['--output'], 'a+') as fp:
                fp.write(metadata + '\n')
        else:
            try:
                sys.stderr.write(metadata + '\n')
            except IOError:
                break
    sys.exit(0)
