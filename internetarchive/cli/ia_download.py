"""Download files from Archive.org.

usage:
    ia download <identifier> [<file>]... [options]...
    ia download --itemlist=<file> [options]...
    ia download --search=<query> [options]...
    ia download --help

options:
    -h, --help
    -v, --verbose               Turn on verbose output [default: False].
    -q, --silent                Turn off ia's output [default: False].
    -d, --dry-run               Print URLs to stdout and exit.
    -i, --ignore-existing       Clobber files already downloaded.
    -C, --checksum              Skip files based on checksum [default: False].
    -R, --retries=<retries>     Set number of retries to <retries> [default: 5]
    -I, --itemlist=<file>       Download items from a specified file. Itemlists should
                                be a plain text file with one identifier per line.
    -S, --search=<query>        Download items returned from a specified search query.
    -g, --glob=<pattern>        Only download files whose filename matches the
                                given glob pattern.
    -f, --format=<format>...    Only download files of the specified format(s).
                                You can use the following command to retrieve
                                a list of file formats contained within a given
                                item:

                                    ia metadata --formats <identifier>

    --no-directories            Download files into working directory. Do not
                                create item directories.
    --destdir=<dir>             The destination directory to download files
                                and item directories to.
"""
from __future__ import print_function, absolute_import
import os
import sys

import six
from docopt import docopt, printable_usage
from schema import Schema, Use, Or, And, SchemaError

from internetarchive import search_items


def itemlist_ids(itemlist):
    for line in open(itemlist):
        yield line.strip()


def search_ids(query):
    for doc in search_items(query):
        yield doc.get('identifier')


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
    })

    # Filenames should be unicode literals. Support PY2 and PY3.
    if six.PY2:
        args['<file>'] = [f.decode('utf-8') for f in args['<file>']]

    try:
        args = s.validate(args)
    except SchemaError as exc:
        sys.stderr.write('{0}\n{1}\n'.format(
            str(exc), printable_usage(__doc__)))
        sys.exit(1)

    retries = int(args['--retries'])

    if args['--itemlist']:
        ids = [x.strip() for x in open(args['--itemlist'])]
        total_ids = len(ids)
    elif args['--search']:
        _search = search_items(args['--search'])
        total_ids = _search.num_found
        ids = search_ids(args['--search'])

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
        identifier = identifier.strip()
        if total_ids > 1:
            item_index = '{0}/{1}'.format((i + 1), total_ids)
        else:
            item_index = None

        try:
            item = session.get_item(identifier)
        except Exception as exc:
            print('{0}: failed to retrieve item metadata - errors'.format(identifier))
            continue

        # Otherwise, download the entire item.
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
            ignore_errors=True
        )
        if _errors:
            errors.append(_errors)
    if errors:
        # TODO: add option for a summary/report.
        sys.exit(1)
    else:
        sys.exit(0)
