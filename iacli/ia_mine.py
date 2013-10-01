"""Concurrently download metadata for items on Archive.org.

usage:
    ia mine <itemlist.txt> [options...]

options:
    -h, --help  
    -v, --verbose  
    -w, --workers=<count>  The number requests to run concurrently 
                           [default: 20].

"""
from docopt import docopt
import sys
import json

import internetarchive



# ia_mine()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    identifiers = [i.strip() for i in open(args['<itemlist.txt>'])]
    workers = int(args.get('--workers', 20)[0])
    miner = internetarchive.get_data_miner(identifiers, workers=workers)
    for i, item in miner.items():
        sys.stdout.write('saving metadata for: {0}\n'.format(item.identifier))
        with open('{0}_meta.json'.format(item.identifier), 'w') as fp:
            json.dump(item.metadata, fp)
