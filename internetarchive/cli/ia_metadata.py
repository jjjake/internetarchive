#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2021 Internet Archive
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
                                [--timeout=<value>] [--expect=<key:value>...]
    ia metadata <identifier>... --remove=<key:value>... [--priority=<priority>]
                                [--header=<key:value>...] [--timeout=<value>]
                                [--expect=<key:value>...]
    ia metadata <identifier>... [--append=<key:value>... | --append-list=<key:value>...]
                                [--priority=<priority>] [--target=<target>]
                                [--header=<key:value>...] [--timeout=<value>]
                                [--expect=<key:value>...]
    ia metadata <identifier>... --insert=<key:value>... [--priority=<priority>]
                                [--target=<target>] [--header=<key:value>...]
                                [--timeout=<value>] [--expect=<key:value>...]
    ia metadata --spreadsheet=<metadata.csv> [--priority=<priority>]
                [--modify=<key:value>...] [--header=<key:value>...] [--timeout=<value>]
                [--expect=<key:value>...]
    ia metadata --help

options:
    -h, --help
    -m, --modify=<key:value>            Modify the metadata of an item.
    -H, --header=<key:value>...         S3 HTTP headers to send with your request.
    -t, --target=<target>               The metadata target to modify.
    -a, --append=<key:value>...         Append a string to a metadata element.
    -A, --append-list=<key:value>...    Append a field to a metadata element.
    -i, --insert=<key:value>...         Insert a value into a multi-value field given
                                        an index (e.g. `--insert=collection[0]:foo`).
    -E, --expect=<key:value>...         Test an expectation server-side before applying
                                        patch to item metadata.
    -s, --spreadsheet=<metadata.csv>    Modify metadata in bulk using a spreadsheet as
                                        input.
    -e, --exists                        Check if an item exists
    -F, --formats                       Return the file-formats the given item contains.
    -p, --priority=<priority>           Set the task priority.
    -r, --remove=<key:value>...         Remove <key:value> from a metadata element.
                                        Works on both single and multi-field metadata
                                        elements.
    --timeout=<value>                   Set a timeout for metadata writes.
"""
from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict
from copy import copy
from typing import Mapping

from docopt import docopt, printable_usage
from requests import Response
from schema import And, Or, Schema, SchemaError, Use  # type: ignore[import]

from internetarchive import item, session
from internetarchive.cli.argparser import (
    get_args_dict,
    get_args_dict_many_write,
    get_args_header_dict,
)
from internetarchive.exceptions import ItemLocateError
from internetarchive.utils import json


def modify_metadata(item: item.Item, metadata: Mapping, args: Mapping) -> Response:
    append = bool(args['--append'])
    expect = get_args_dict(args['--expect'])
    append_list = bool(args['--append-list'])
    insert = bool(args['--insert'])
    try:
        r = item.modify_metadata(metadata, target=args['--target'], append=append,
                                 expect=expect, priority=args['--priority'],
                                 append_list=append_list, headers=args['--header'],
                                 insert=insert, timeout=args['--timeout'], refresh=False)
        assert isinstance(r, Response)  # mypy: modify_metadata() -> Request | Response
    except ItemLocateError as exc:
        print(f'{item.identifier} - error: {exc}', file=sys.stderr)
        sys.exit(1)
    if not r.json()['success']:
        error_msg = r.json()['error']
        etype = 'warning' if 'no changes' in r.text else 'error'
        print(f'{item.identifier} - {etype} ({r.status_code}): {error_msg}', file=sys.stderr)
        return r
    print(f'{item.identifier} - success: {r.json()["log"]}', file=sys.stderr)
    return r


def remove_metadata(item: item.Item, metadata: Mapping, args: Mapping) -> Response:
    md: dict[str, list | str] = defaultdict(list)
    for key in metadata:
        src_md = copy(item.metadata.get(key))
        if not src_md:
            print(f'{item.identifier}/metadata/{key} does not exist, skipping.', file=sys.stderr)
            continue

        if key == 'collection':
            _col = copy(metadata[key])
            _src_md = copy(src_md)
            if not isinstance(_col, list):
                _col = [_col]
            if not isinstance(_src_md, list):
                _src_md = [_src_md]
            for c in _col:
                if c not in _src_md:
                    r = item.remove_from_simplelist(c, 'holdings')
                    j = r.json()
                    if j.get('success'):
                        print(f'{item.identifier} - success: {item.identifier} no longer in {c}',
                              file=sys.stderr)
                        sys.exit(0)
                    elif j.get('error', '').startswith('no row to delete for'):
                        print(f'{item.identifier} - success: {item.identifier} no longer in {c}',
                              file=sys.stderr)
                        sys.exit(0)
                    else:
                        print(f'{item.identifier} - error: {j.get("error")}', file=sys.stderr)
                        sys.exit(1)

        if not isinstance(src_md, list):
            if key == 'subject':
                src_md = src_md.split(';')
            elif key == 'collection':
                print(f'{item.identifier} - error: all collections would be removed, '
                      'not submitting task.', file=sys.stderr)
                sys.exit(1)

            if src_md == metadata[key]:
                md[key] = 'REMOVE_TAG'
                continue

        for x in src_md:
            if isinstance(metadata[key], list):
                if x not in metadata[key]:
                    md[key].append(x)  # type: ignore
            else:
                if x != metadata[key]:
                    md[key].append(x)  # type: ignore

        if len(md[key]) == len(src_md):
            del md[key]

        # Workaround to avoid empty lists or strings as values.
        # TODO: Shouldn't the metadata api handle this?
        if len(src_md) == 1 and metadata[key] in src_md:
            md[key] = 'REMOVE_TAG'

    if md.get('collection') == []:
        print(f'{item.identifier} - error: all collections would be removed, not submitting task.',
              file=sys.stderr)
        sys.exit(1)
    elif not md:
        print(f'{item.identifier} - warning: nothing needed to be removed.', file=sys.stderr)
        sys.exit(0)

    r = modify_metadata(item, md, args)
    return r


def main(argv: dict, session: session.ArchiveSession) -> None:
    args = docopt(__doc__, argv=argv)

    # Validate args.
    s = Schema({
        str: bool,
        '<identifier>': list,
        '--modify': list,
        '--expect': list,
        '--header': Or(None, And(Use(get_args_header_dict), dict),
               error='--header must be formatted as --header="key:value"'),
        '--append': list,
        '--append-list': list,
        '--insert': list,
        '--remove': list,
        '--spreadsheet': Or(None, And(lambda f: os.path.exists(f),
                            error='<file> should be a readable file or directory.')),
        '--target': Or(None, str),
        '--priority': Or(None, Use(int, error='<priority> should be an integer.')),
        '--timeout': Or(None, str),
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print(f'{exc}\n{printable_usage(__doc__)}', file=sys.stderr)
        sys.exit(1)

    formats = set()
    responses: list[bool | Response] = []

    for i, identifier in enumerate(args['<identifier>']):
        item = session.get_item(identifier)

        # Check existence of item.
        if args['--exists']:
            if item.exists:
                responses.append(True)
                print(f'{identifier} exists', file=sys.stderr)
            else:
                responses.append(False)
                print(f'{identifier} does not exist', file=sys.stderr)
            if (i + 1) == len(args['<identifier>']):
                if all(r is True for r in responses):
                    sys.exit(0)
                else:
                    sys.exit(1)

        # Modify metadata.
        elif (args['--modify'] or args['--append'] or args['--append-list']
              or args['--remove'] or args['--insert']):
            if args['--modify']:
                metadata_args = args['--modify']
            elif args['--append']:
                metadata_args = args['--append']
            elif args['--append-list']:
                metadata_args = args['--append-list']
            elif args['--insert']:
                metadata_args = args['--insert']
            if args['--remove']:
                metadata_args = args['--remove']
            try:
                metadata = get_args_dict(metadata_args)
                if any('/' in k for k in metadata):
                    metadata = get_args_dict_many_write(metadata)
            except ValueError:
                print('error: The value of --modify, --remove, --append, --append-list '
                      'or --insert is invalid. It must be formatted as: '
                      '--modify=key:value',
                      file=sys.stderr)
                sys.exit(1)

            if args['--remove']:
                responses.append(remove_metadata(item, metadata, args))
            else:
                responses.append(modify_metadata(item, metadata, args))
            if (i + 1) == len(args['<identifier>']):
                if all(r.status_code == 200 for r in responses):  # type: ignore
                    sys.exit(0)
                else:
                    for r in responses:
                        assert isinstance(r, Response)
                        if r.status_code == 200:
                            continue
                        # We still want to exit 0 if the non-200 is a
                        # "no changes to xml" error.
                        elif 'no changes' in r.text:
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
            metadata_str = json.dumps(item.item_metadata)
            print(metadata_str)

    # Edit metadata for items in bulk, using a spreadsheet as input.
    if args['--spreadsheet']:
        if not args['--priority']:
            args['--priority'] = -5
        with open(args['--spreadsheet'], newline='', encoding='utf-8') as csvfp:
            spreadsheet = csv.DictReader(csvfp)
            responses = []
            for row in spreadsheet:
                if not row['identifier']:
                    continue
                item = session.get_item(row['identifier'])
                if row.get('file'):
                    del row['file']
                metadata = {k.lower(): v for k, v in row.items() if v}
                responses.append(modify_metadata(item, metadata, args))

            if all(r.status_code == 200 for r in responses):  # type: ignore
                sys.exit(0)
            else:
                for r in responses:
                    assert isinstance(r, Response)
                    if r.status_code == 200:
                        continue
                    # We still want to exit 0 if the non-200 is a
                    # "no changes to xml" error.
                    elif 'no changes' in r.text:
                        continue
                    else:
                        sys.exit(1)
