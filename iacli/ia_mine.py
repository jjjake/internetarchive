"""Concurrently download metadata for items on Archive.org.

usage:
    ia mine <itemlist.txt> [options...]

options:
    -h, --help  
    -v, --verbose  
    -t, --target=<target>...    Metadata target to retrieve. This option will output 
                                metadata as tab-separated fields instead of JSON.
    -c, --cache                 Write item metadta to a file called <identifier>_meta.json
    -o, --output=<output.json>  Write all metadata to a single output file <itemlist>.json
    -w, --workers=<count>       The number requests to run concurrently [default: 20].

"""
import os
from sys import stdout, stderr, exit
from json import dump, dumps

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
        open(args['--output'][0], 'w').close()

    for i, item in miner.items():

        # Filter metadta.
        if args['--target']:
            metadata = []
            for target in args['--target']:
                for i, t in enumerate(target.split('/')):
                    if i == 0:
                        md = item.metadata.get(t)
                    else:
                        md = md.get(t)
                if md:
                    metadata.append(md)
            metadata = '\t'.join(metadata)
        else:
            metadata = dumps(item.metadata)

        # Output/cache metadata.
        if args['--cache']:
            stdout.write('saving metadata for: {0}\n'.format(item.identifier))
            with open('{0}_meta.json'.format(item.identifier), 'w') as fp:
                fp.write(metadata)
        elif args['--output']:
            stdout.write('saving metadata for: {0}\n'.format(item.identifier))
            with open(args['--output'][0], 'a+') as fp:
                fp.write(metadata + '\n')
        else:
            stdout.write(metadata + '\n')

    exit(0)
