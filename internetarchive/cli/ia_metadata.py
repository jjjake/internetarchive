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

"""Retrieve and modify Archive.org metadata.

usage:
    ia metadata <identifier>... [--exists | --formats] [--header=<key:value>...]
    ia metadata <identifier>... --modify=<key:value>... [--target=<target>]
                                [--priority=<priority>] [--header=<key:value>...]
    ia metadata <identifier>... --remove=<key:value>... [--priority=<priority>]
                                [--header=<key:value>...]
    ia metadata <identifier>... [--append=<key:value>... | --append-list=<key:value>...]
                                [--priority=<priority>] [--target=<target>]
                                [--header=<key:value>...]
    ia metadata --spreadsheet=<metadata.csv> [--priority=<priority>]
                [--modify=<key:value>...] [--header=<key:value>...]
    ia metadata --help

options:
    -h, --help
    -m, --modify=<key:value>            Modify the metadata of an item.
    -H, --header=<key:value>...         S3 HTTP headers to send with your request.
    -t, --target=<target>               The metadata target to modify.
    -a, --append=<key:value>...         Append a string to a metadata element.
    -A, --append-list=<key:value>...    Append a field to a metadata element.
    -s, --spreadsheet=<metadata.csv>    Modify metadata in bulk using a spreadsheet as
                                        input.
    -e, --exists                        Check if an item exists
    -F, --formats                       Return the file-formats the given item contains.
    -p, --priority=<priority>           Set the task priority.
    -r, --remove=<key:value>...         Remove <key:value> from a metadata element.
                                        Works on both single and multi-field metadata
                                        elements.
"""
from __future__ import absolute_import, unicode_literals, print_function
import sys
import os
try:
    import ujson as json
except ImportError:
    import json
import io
from collections import defaultdict
from copy import copy

from docopt import docopt, printable_usage
from schema import Schema, SchemaError, Or, And, Use
import six

from internetarchive.cli.argparser import get_args_dict, get_args_dict_many_write,\
    get_args_header_dict
from internetarchive.exceptions import ItemLocateError

# Only import backports.csv for Python2 (in support of FreeBSD port).
PY2 = sys.version_info[0] == 2
if sys.version_info[0] == 2:
    from backports import csv
else:
    import csv


def modify_metadata(item, metadata, args):
    append = True if args['--append'] else False
    append_list = True if args['--append-list'] else False
    try:
        r = item.modify_metadata(metadata, target=args['--target'], append=append,
                                 priority=args['--priority'], append_list=append_list,
                                 headers=args['--header'])
    except ItemLocateError as exc:
        print('{} - error: {}'.format(item.identifier, str(exc)), file=sys.stderr)
        sys.exit(1)
    if not r.json()['success']:
        error_msg = r.json()['error']
        if 'no changes' in r.content.decode('utf-8'):
            etype = 'warning'
        else:
            etype = 'error'
        print('{0} - {1} ({2}): {3}'.format(
            item.identifier, etype, r.status_code, error_msg), file=sys.stderr)
        return r
    print('{0} - success: {1}'.format(item.identifier, r.json()['log']))
    return r


def remove_metadata(item, metadata, args):
    md = defaultdict(list)
    for key in metadata:
        src_md = copy(item.metadata.get(key))
        if not src_md:
            print('{0}/metadata/{1} does not exist, skipping.'.format(
                item.identifier, key), file=sys.stderr)
            continue
        elif key == 'collection' and metadata[key] not in src_md:
            r = item.remove_from_simplelist(metadata[key], 'holdings')
            j = r.json()
            if j.get('success'):
                print('{} - success: {} no longer in {}'.format(
                      item.identifier, item.identifier, metadata[key]))
                sys.exit(0)
            elif j.get('error', '').startswith('no row to delete for'):
                print('{} - success: {} no longer in {}'.format(
                      item.identifier, item.identifier, metadata[key]))
                sys.exit(0)
            else:
                print('{} - error: {}'.format(item.identifier, j.get('error')))
            sys.exit()
        elif not isinstance(src_md, list):
            if key == 'subject':
                src_md = src_md.split(';')
            elif key == 'collection':
                print('{} - error: all collections would be removed, '
                      'not submitting task.'.format(item.identifier), file=sys.stderr)
                sys.exit(1)

            if src_md == metadata[key]:
                md[key] = 'REMOVE_TAG'
                continue

        for x in src_md:
            if x not in metadata[key]:
                md[key].append(x)

        if len(md[key]) == len(src_md):
            del md[key]

        # Workaround to avoid empty lists or strings as values.
        # TODO: Shouldn't the metadata api handle this?
        if len(src_md) == 1 and metadata[key] in src_md:
            md[key] = 'REMOVE_TAG'

    if md.get('collection') == []:
        print('{} - error: all collections would be removed, not submitting task.'.format(
            item.identifier), file=sys.stderr)
        sys.exit(1)
    elif not md:
        print('{} - warning: nothing needed to be removed.'.format(
            item.identifier), file=sys.stderr)
        sys.exit(0)

    r = modify_metadata(item, md, args)
    return r


def main(argv, session):
    args = docopt(__doc__, argv=argv)

    # Validate args.
    s = Schema({
        six.text_type: bool,
        '<identifier>': list,
        '--modify': list,
        '--header': Or(None, And(Use(get_args_header_dict), dict),
               error='--header must be formatted as --header="key:value"'),
        '--append': list,
        '--append-list': list,
        '--remove': list,
        '--spreadsheet': Or(None, And(lambda f: os.path.exists(f),
                            error='<file> should be a readable file or directory.')),
        '--target': Or(None, str),
        '--priority': Or(None, Use(int, error='<priority> should be an integer.')),
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
        elif args['--modify'] or args['--append'] or args['--append-list'] \
                or args['--remove']:
            if args['--modify']:
                metadata_args = args['--modify']
            elif args['--append']:
                metadata_args = args['--append']
            elif args['--append-list']:
                metadata_args = args['--append-list']
            if args['--remove']:
                metadata_args = args['--remove']
            try:
                metadata = get_args_dict(metadata_args)
                if any('/' in k for k in metadata):
                    metadata = get_args_dict_many_write(metadata)
            except ValueError:
                print("error: The value of --modify, --remove, --append or --append-list "
                      "is invalid. It must be formatted as: --modify=key:value",
                      file=sys.stderr)
                sys.exit(1)

            if args['--remove']:
                responses.append(remove_metadata(item, metadata, args))
            else:
                responses.append(modify_metadata(item, metadata, args))
            if (i + 1) == len(args['<identifier>']):
                if all(r.status_code == 200 for r in responses):
                    sys.exit(0)
                else:
                    for r in responses:
                        if r.status_code == 200:
                            continue
                        # We still want to exit 0 if the non-200 is a
                        # "no changes to xml" error.
                        elif 'no changes' in r.content.decode('utf-8'):
                            continue
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
        with io.open(args['--spreadsheet'], 'rU', newline='', encoding='utf-8') as csvfp:
            spreadsheet = csv.DictReader(csvfp)
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
                for r in responses:
                    if r.status_code == 200:
                        continue
                    # We still want to exit 0 if the non-200 is a
                    # "no changes to xml" error.
                    elif 'no changes' in r.content.decode('utf-8'):
                        continue
                    else:
                        sys.exit(1)
