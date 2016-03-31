# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2016 Internet Archive
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

"""Retrieve and modify Archive.org metadata.

usage:
    ia metadata <identifier>... [--modify=<key:value>...] [--target=<target>]
                                [--priority=<priority>]
    ia metadata <identifier>... [--append=<key:value>...] [--priority=<priority>]
    ia metadata <identifier>... [--exists | --formats]
    ia metadata --spreadsheet=<metadata.csv> [--priority=<priority>]
                                             [--modify=<key:value>...]
    ia metadata --help

options:
    -h, --help
    -m, --modify=<key:value>          Modify the metadata of an item.
    -t, --target=<target>             The metadata target to modify.
    -a, --append=<key:value>          Append metadata to an element.
    -s, --spreadsheet=<metadata.csv>  Modify metadata in bulk using a spreadsheet as
                                      input.
    -e, --exists                      Check if an item exists
    -F, --formats                     Return the file-formats the given item contains.
    -p, --priority=<priority>         Set the task priority.
"""
from __future__ import absolute_import, unicode_literals, print_function
import sys
import os
try:
    import ujson as json
except ImportError:
    import json
import csv

from docopt import docopt, printable_usage
from schema import Schema, SchemaError, Or, And
import six

from internetarchive.cli.argparser import get_args_dict


def modify_metadata(item, metadata, args):
    append = True if args['--append'] else False
    r = item.modify_metadata(metadata, target=args['--target'], append=append,
                             priority=args['--priority'])
    if not r.json()['success']:
        error_msg = r.json()['error']
        print('{0} - error ({1}): {2}'.format(item.identifier, r.status_code, error_msg),
              file=sys.stderr)
        return r
    print('{0} - success: {1}'.format(item.identifier, r.json()['log']))
    return r


def main(argv, session):
    args = docopt(__doc__, argv=argv)

    # Validate args.
    s = Schema({
        six.text_type: bool,
        '<identifier>': list,
        '--modify': list,
        '--append': list,
        '--spreadsheet': Or(None, And(lambda f: os.path.exists(f),
                            error='<file> should be a readable file or directory.')),
        '--target': Or(None, str),
        '--priority': None,
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print('{0}\n{1}'.format(str(exc), printable_usage(__doc__)), file=sys.stderr)
        sys.exit(1)

    formats = set()
    responses = []

    for i, identifier in enumerate(args['<identifier>']):
        item = session.get_item(identifier)

        # Check existence of item.
        if args['--exists']:
            if item.exists:
                responses.append(True)
                print('{0} exists'.format(identifier))
            else:
                responses.append(False)
                print('{0} does not exist'.format(identifier), file=sys.stderr)
            if (i + 1) == len(args['<identifier>']):
                if all(r is True for r in responses):
                    sys.exit(0)
                else:
                    sys.exit(1)

        # Modify metadata.
        elif args['--modify'] or args['--append']:
            metadata_args = args['--modify'] if args['--modify'] else args['--append']
            metadata = get_args_dict(metadata_args)
            responses.append(modify_metadata(item, metadata, args))
            if (i + 1) == len(args['<identifier>']):
                if all(r.status_code == 200 for r in responses):
                    sys.exit(0)
                else:
                    sys.exit(1)

        # Get metadata.
        elif args['--formats']:
            for f in item.get_files():
                formats.add(f.format)
            if (i + 1) == len(args['<identifier>']):
                print('\n'.join(formats))

        # Dump JSON to stdout.
        else:
            metadata = json.dumps(item.item_metadata)
            print(metadata)

    # Edit metadata for items in bulk, using a spreadsheet as input.
    if args['--spreadsheet']:
        if not args['--priority']:
            args['--priority'] = -5
        spreadsheet = csv.DictReader(open(args['--spreadsheet'], 'rU'))
        responses = []
        for row in spreadsheet:
            if not row['identifier']:
                continue
            item = session.get_item(row['identifier'])
            if row.get('file'):
                del row['file']
            metadata = dict((k.lower(), v) for (k, v) in row.items() if v)
            responses.append(modify_metadata(item, metadata, args))

        if all(r.status_code == 200 for r in responses):
            sys.exit(0)
        else:
            sys.exit(1)

    sys.exit(0)
