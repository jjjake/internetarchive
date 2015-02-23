"""Search the Internet Archive using the Archive.org Advanced Search
API <https://archive.org/advancedsearch.php#raw>.

usage:
    ia search [--parameters=<key:value>...] [--sort=<field:order>...]
              [--itemlist | --field=<field>...] [--number-found] [--v2] <query>...
    ia search --help

options:
    -h, --help
    -p, --parameters=<key:value>...  Parameters to send with your query.
    -s, --sort=<field:order>...      Sort search results by specified fields.
                                     <order> can be either "asc" for ascending
                                     and "desc" for descending.
    -i, --itemlist                   Output identifiers only.
    -f, --field=<field>...           Metadata fields to return.
    -n, --number-found               Print the number of results to stdout.
    --v2                             Search https://archive.org/v2.

"""
import sys
try:
    import ujson as json
except ImportError:
    import json

from docopt import docopt

from internetarchive import search_items


# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    params = dict(p.split(':') for p in args['--parameters'])

    # format sort paramaters.
    if args['--sort']:
        for i, field in enumerate(args['--sort']):
            key = 'sort[{0}]'.format(i)
            params[key] = field.strip().replace(':', ' ')

    query = ' '.join(args['<query>'])
    if args['--itemlist']:
        fields = ['identifier']
    else:
        fields = args['--field']
    search = search_items(query, fields=args['--field'], params=params, v2=args['--v2'])
    if args['--number-found']:
        sys.stdout.write('{0}\n'.format(search.num_found))
        sys.exit(0)
    for result in search:
        try:
            if args['--itemlist']:
                sys.stdout.write(result.get('identifier', ''))
            else:
                json.dump(result, sys.stdout)
            sys.stdout.write('\n')
        except IOError:
            sys.exit(0)
