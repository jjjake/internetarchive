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

"""Download files from Archive.org.

usage:
    ia download <identifier> [<file>]... [options]...
    ia download <identifier> <file> --stdout [--retries=<retries>]
    ia download --itemlist=<file> [options]...
    ia download --search=<query> [options]...
    ia download --help

options:
    -h, --help
    -v, --verbose                            Turn on verbose output [default: False].
    -q, --silent                             Turn off ia's output [default: False].
    -d, --dry-run                            Print URLs to stdout and exit.
    -i, --ignore-existing                    Clobber files already downloaded.
    -C, --checksum                           Skip files based on checksum [default: False].
    -R, --retries=<retries>                  Set number of retries to <retries> [default: 5].
    -I, --itemlist=<file>                    Download items from a specified file. Itemlists should
                                             be a plain text file with one identifier per line.
    -S, --search=<query>                     Download items returned from a specified search query.
    -P, --search-parameters=<key:value>...   Download items returned from a specified search query.
    -g, --glob=<pattern>                     Only download files whose filename matches the
                                             given glob pattern.
    -f, --format=<format>...                 Only download files of the specified format(s).
                                             You can use the following command to retrieve
                                             a list of file formats contained within a given
                                             item:

                                                 ia metadata --formats <identifier>

    --on-the-fly                             Download on-the-fly files, as well as other matching
                                             files. on-the-fly files include derivative EPUB, MOBI
                                             and DAISY files [default: False].
    --no-directories                         Download files into working directory. Do not
                                             create item directories.
    --destdir=<dir>                          The destination directory to download files
                                             and item directories to.
    -s, --stdout                             Write file contents to stdout.
    --no-change-timestamp                    Don't change the timestamp of downloaded files to reflect
                                             the source material.
    -p, --parameters=<key:value>...          Parameters to send with your query (e.g. `cnt=0`).
    -a, --download-history                   Do not download any files from the history dir.
"""
from __future__ import print_function, absolute_import
import os
import sys

import six
from docopt import docopt, printable_usage
from schema import Schema, Use, Or, And, SchemaError

from internetarchive.cli.argparser import get_args_dict


def dir_exists(dir):
    if os.path.exists(dir):
        return True
    else:
        return False


def main(argv, session):
    args = docopt(__doc__, argv=argv)

    # Validation error messages.
    destdir_msg = '--destdir must be a valid path to a directory.'
    itemlist_msg = '--itemlist must be a valid path to an existing file.'

    # Validate args.
    s = Schema({
        str: Use(bool),
        '--destdir': Or([], And(Use(lambda d: d[0]), dir_exists), error=destdir_msg),
        '--format': list,
        '--glob': Use(lambda l: l[0] if l else None),
        '<file>': list,
        '--search': Or(str, None),
        '--itemlist': Or(None, And(lambda f: os.path.isfile(f)), error=itemlist_msg),
        '<identifier>': Or(str, None),
        '--retries': Use(lambda x: x[0]),
        '--search-parameters': Use(lambda x: get_args_dict(x, query_string=True)),
        '--on-the-fly': Use(bool),
        '--no-change-timestamp': Use(bool),
        '--download-history': Use(bool),
        '--parameters': Use(lambda x: get_args_dict(x, query_string=True)),
    })

    # Filenames should be unicode literals. Support PY2 and PY3.
    if six.PY2:
        args['<file>'] = [f.decode('utf-8') for f in args['<file>']]

    try:
        args = s.validate(args)
        if args['--glob']:
            if args['--format']:
                raise(SchemaError(None, '--glob and --format cannot be used together.'))

    except SchemaError as exc:
        print('{0}\n{1}'.format(
            str(exc), printable_usage(__doc__)), file=sys.stderr)
        sys.exit(1)

    retries = int(args['--retries'])

    if args['--itemlist']:
        with open(args['--itemlist']) as fp:
            ids = [x.strip() for x in fp]
        total_ids = len(ids)
    elif args['--search']:
        try:
            _search = session.search_items(args['--search'],
                                           params=args['--search-parameters'])
            total_ids = _search.num_found
            if total_ids == 0:
                print('error: the query "{0}" returned no results'.format(
                    args['--search']), file=sys.stderr)
                sys.exit(1)
            ids = _search
        except ValueError as e:
            print('error: {0}'.format(e), file=sys.stderr)
            sys.exit(1)

    # Download specific files.
    if args['<identifier>'] and args['<identifier>'] != '-':
        if '/' in args['<identifier>']:
            identifier = args['<identifier>'].split('/')[0]
            files = ['/'.join(args['<identifier>'].split('/')[1:])]
        else:
            identifier = args['<identifier>']
            files = args['<file>']
        total_ids = 1
        ids = [identifier]
    elif args['<identifier>'] == '-':
        total_ids = 1
        ids = sys.stdin
        files = None
    else:
        files = None

    errors = list()
    for i, identifier in enumerate(ids):
        if args['--stdout']:
            item = session.get_item(identifier)
            f = list(item.get_files(args['<file>']))
            try:
                assert len(f) == 1
            except AssertionError:
                print('error: {0}/{1} does not exist!'.format(
                    identifier, args['<file>'][0]), file=sys.stderr)
                sys.exit(1)
            if six.PY2:
                stdout_buf = sys.stdout
            else:
                stdout_buf = sys.stdout.buffer
            f[0].download(retries=args['--retries'],
                          fileobj=stdout_buf,
                          params=args['--parameters'])
            sys.exit(0)
        try:
            identifier = identifier.strip()
        except AttributeError:
            identifier = identifier.get('identifier')
        if total_ids > 1:
            item_index = '{0}/{1}'.format((i + 1), total_ids)
        else:
            item_index = None

        try:
            item = session.get_item(identifier)
        except Exception as exc:
            print('{0}: failed to retrieve item metadata - errors'.format(identifier),
                  file=sys.stderr)
            if 'You are attempting to make an HTTPS' in str(exc):
                print('\n{0}'.format(exc), file=sys.stderr)
                sys.exit(1)
            else:
                continue

        # Otherwise, download the entire item.
        ignore_history_dir = True if not args['--download-history'] else False
        _errors = item.download(
            files=files,
            formats=args['--format'],
            glob_pattern=args['--glob'],
            dry_run=args['--dry-run'],
            verbose=args['--verbose'],
            silent=args['--silent'],
            ignore_existing=args['--ignore-existing'],
            checksum=args['--checksum'],
            destdir=args['--destdir'],
            no_directory=args['--no-directories'],
            retries=retries,
            item_index=item_index,
            ignore_errors=True,
            on_the_fly=args['--on-the-fly'],
            no_change_timestamp=args['--no-change-timestamp'],
            params=args['--parameters'],
            ignore_history_dir=ignore_history_dir,
        )
        if _errors:
            errors.append(_errors)
    if errors:
        # TODO: add option for a summary/report.
        sys.exit(1)
    else:
        sys.exit(0)
