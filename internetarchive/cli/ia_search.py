# -*- coding: utf-8 -*-
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
    -t, --timeout=<seconds>          Set the timeout in seconds [default: 300].
"""
from __future__ import absolute_import, print_function, unicode_literals
import sys
try:
    import ujson as json
except ImportError:
    import json
from itertools import chain

from docopt import docopt, printable_usage
from schema import Schema, SchemaError, Use, Or, And
import six
from requests.exceptions import ConnectTimeout

from internetarchive import search_items
from internetarchive.cli.argparser import get_args_dict
from internetarchive.exceptions import AuthenticationError


def main(argv, session=None):
    args = docopt(__doc__, argv=argv)

    # Validate args.
    s = Schema({
        six.text_type: Use(bool),
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
        print('{0}\n{1}'.format(str(exc), printable_usage(__doc__)), file=sys.stderr)
        sys.exit(1)

    # Support comma separated values.
    fields = list(chain.from_iterable([x.split(',') for x in args['--field']]))
    sorts = list(chain.from_iterable([x.split(',') for x in args['--sort']]))

    r_kwargs = dict(
        headers=args['--header'],
        timeout=args['--timeout'],
    )

    search = session.search_items(args['<query>'],
                                  fields=fields,
                                  sorts=sorts,
                                  params=args['--parameters'],
                                  request_kwargs=r_kwargs)

    try:
        if args['--num-found']:
            print('{0}'.format(search.num_found))
            sys.exit(0)

        for result in search:
            if args['--itemlist']:
                print(result.get('identifier', ''))
            else:
                j = json.dumps(result)
                print(j)
    except ValueError as e:
        print('error: {0}'.format(e), file=sys.stderr)
    except ConnectTimeout as exc:
        print('error: Request timed out. Increase the --timeout and try again.',
              file=sys.stderr)
        sys.exit(1)
    except AuthenticationError as exc:
        print('error: {}'.format(exc), file=sys.stderr)
        sys.exit(1)
