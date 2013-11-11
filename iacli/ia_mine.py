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
from sys import stdout, exit
from json import dumps

from docopt import docopt

from internetarchive import get_data_miner



# ia_mine()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    identifiers = [i.strip() for i in open(args['<itemlist.txt>'])]
    workers = int(args.get('--workers', 20)[0])
    miner = get_data_miner(identifiers, workers=workers)

    # If writing all metadata to a single output file, make sure that 
    # file is empty.
    if args['--output']:
        open(args['--output'], 'w').close()

    for i, item in miner.items():
        metadata = dumps(item.metadata)
        if args['--cache']:
            stdout.write('saving metadata for: {0}\n'.format(item.identifier))
            with open('{0}_meta.json'.format(item.identifier), 'w') as fp:
                fp.write(metadata)
        elif args['--output']:
            stdout.write('saving metadata for: {0}\n'.format(item.identifier))
            with open(args['--output'], 'a+') as fp:
                fp.write(metadata + '\n')
        else:
            stdout.write(metadata + '\n')
    exit(0)
