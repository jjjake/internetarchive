"""
usage:
    ia mine <itemlist.txt> [options...]

options:
    -h, --help  
    -v, --verbose  
    -f, --files  
    -w, --workers=<count>  [default: 20]
    -c, --cache            

"""
from docopt import docopt
import sys
import json

import internetarchive



# ia_mine()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    items = [i.strip() for i in open(args['<itemlist.txt>'])]
    workers = int(args.get('--workers', 20)[0])
    miner = internetarchive.Mine(items, workers=workers)
    for i, item in miner.items():
        if args['--cache']:
            sys.stdout.write('saving metadata for: {0}\n'.format(item.identifier))
            with open('{0}_meta.json'.format(item.identifier), 'w') as fp:
                json.dump(item.metadata, fp)
        else:
            sys.stdout.write(item.metadata)
