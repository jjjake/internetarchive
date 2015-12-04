"""Search items on Archive.org.

usage:
    ia search <query>... [options]...
    ia search --help

options:
    -h, --help
    -p, --parameters=<key:value>...  Parameters to send with your query.
    -s, --sort=<field:order>...      Sort search results by specified fields.
                                     <order> can be either "asc" for ascending
                                     and "desc" for descending.
    -i, --itemlist                   Output identifiers only.
    -f, --field=<field>...           Metadata fields to return.
    -n, --num-found                  Print the number of results to stdout.
"""
from __future__ import absolute_import, print_function, unicode_literals
import sys
try:
    import ujson as json
except ImportError:
    import json

from docopt import docopt, printable_usage
from schema import Schema, SchemaError, Use
import six

from internetarchive import search_items
from internetarchive.cli.argparser import get_args_dict


def main(argv, session=None):
    args = docopt(__doc__, argv=argv)

    # Validate args.
    s = Schema({
        six.text_type: Use(bool),
        '<query>': Use(lambda x: ' '.join(x)),
        '--parameters': Use(lambda x: get_args_dict(x)),
        '--sort': list,
        '--field': Use(lambda x: ['identifier'] if not x and args['--itemlist'] else x),
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print('{0}\n{1}'.format(str(exc), printable_usage(__doc__)), file=sys.stderr)
        sys.exit(1)

    # Format sort paramaters.
    for i, field in enumerate(args['--sort']):
        key = 'sort[{0}]'.format(i)
        args['--parameters'][key] = field.strip().replace(':', ' ')

    search = search_items(args['<query>'],
                          fields=args['--field'],
                          params=args['--parameters'])

    if args['--num-found']:
        print('{0}'.format(search.num_found))
        sys.exit(0)

    for result in search:
        if args['--itemlist']:
            print(result.get('identifier', ''))
        else:
            j = json.dumps(result)
            print(j)
