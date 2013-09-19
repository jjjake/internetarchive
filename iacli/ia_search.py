"""Search archive.org.

usage: 
    ia search [--help] <query>...
"""
from docopt import docopt
import sys

import internetarchive



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    query = ' '.join(args['<query>'])
    search = internetarchive.Search(query)
    for result in search.results:
        sys.stdout.write(result['identifier'] + '\n')
    sys.exit(0)
