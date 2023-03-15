#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2019 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Search items on Archive.org.

usage:
    ia search <query>... [options]...
    ia search --help

options:
    -h, --help
    -p, --parameters=<key:value>...  Parameters to send with your query.
    -H, --header=<key:value>...      Add custom headers to your search request.
    -s, --sort=<field order>...      Sort search results by specified fields.
                                     <order> can be either "asc" for ascending
                                     and "desc" for descending.
    -i, --itemlist                   Output identifiers only.
    -f, --field=<field>...           Metadata fields to return.
    -n, --num-found                  Print the number of results to stdout.
    -F, --fts                        Beta support for querying the archive.org
                                     full text search API.
    -D, --dsl-fts                    Submit --fts query in dsl [default: False].
    -t, --timeout=<seconds>          Set the timeout in seconds [default: 300].

examples:

    ia search 'collection:nasa' --parameters rows:1
"""
from __future__ import annotations

import sys
from itertools import chain

from docopt import docopt, printable_usage
from requests.exceptions import ConnectTimeout, ReadTimeout
from schema import And, Or, Schema, SchemaError, Use  # type: ignore[import]

from internetarchive import ArchiveSession, search_items
from internetarchive.cli.argparser import get_args_dict
from internetarchive.exceptions import AuthenticationError
from internetarchive.utils import json


def main(argv, session: ArchiveSession | None = None) -> None:
    args = docopt(__doc__, argv=argv)

    # Validate args.
    s = Schema({
        str: Use(bool),
        '<query>': Use(lambda x: ' '.join(x)),
        '--parameters': Use(lambda x: get_args_dict(x, query_string=True)),
        '--header': Or(None, And(Use(get_args_dict), dict),
                       error='--header must be formatted as --header="key:value"'),
        '--sort': list,
        '--field': list,
        '--timeout': Use(lambda x: float(x[0]),
                         error='--timeout must be integer or float.')
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print(f'{exc}\n{printable_usage(__doc__)}', file=sys.stderr)
        sys.exit(1)

    # Support comma separated values.
    fields = list(chain.from_iterable([x.split(',') for x in args['--field']]))
    sorts = list(chain.from_iterable([x.split(',') for x in args['--sort']]))

    r_kwargs = {
        'headers': args['--header'],
        'timeout': args['--timeout'],
    }

    search = session.search_items(args['<query>'],  # type: ignore
                                  fields=fields,
                                  sorts=sorts,
                                  params=args['--parameters'],
                                  full_text_search=args['--fts'],
                                  dsl_fts=args['--dsl-fts'],
                                  request_kwargs=r_kwargs)

    try:
        if args['--num-found']:
            print(search.num_found)
            sys.exit(0)

        for result in search:
            if args['--itemlist']:
                if args['--fts'] or args['--dsl-fts']:
                    print('\n'.join(result.get('fields', {}).get('identifier')))
                else:
                    print(result.get('identifier', ''))
            else:
                j = json.dumps(result)
                print(j)
                if result.get('error'):
                    sys.exit(1)
    except ValueError as e:
        print(f'error: {e}', file=sys.stderr)
    except ConnectTimeout as exc:
        print('error: Request timed out. Increase the --timeout and try again.',
              file=sys.stderr)
        sys.exit(1)
    except ReadTimeout as exc:
        print('error: The server timed out and failed to return all search results,'
              ' please try again', file=sys.stderr)
        sys.exit(1)
    except AuthenticationError as exc:
        print(f'error: {exc}', file=sys.stderr)
        sys.exit(1)
