"""Search the Internet Archive using the Archive.org Advanced Search 
API <https://archive.org/advancedsearch.php#raw>.

usage: 
    ia search [--help] <query>... [options...]

options:
    -h, --help
    -p, --parameters=<key:value>...  Parameters to send with your query.
    -s, --sort=<field:order>...      Sort search results by specified
                                     fields. <order> can be either "asc"
                                     for ascending and "desc" for 
                                     descending.
    -f, --field=<field>...           Metadata fields to return.

"""
from docopt import docopt
import sys

from internetarchive import search



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    params = dict(p.split(':') for p in args['--parameters'])
    if args['--sort']:
        for i, field in enumerate(args['--sort']):
            key = 'sort[{0}]'.format(i)
            params[key] = field.strip().replace(':', ' ')

    fields = ['identifier'] + args['--field']

    query = ' '.join(args['<query>'])
    search_resp = search(query, fields=fields, params=params)
    for result in search_resp.results():
        output = '\t'.join([result[f] for f in fields]).encode('utf-8')
        sys.stdout.write(output + '\n')
    sys.exit(0)
