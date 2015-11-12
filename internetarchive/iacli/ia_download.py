"""Download files from archive.org.

usage:
    ia download [--verbose] [--silent] [--log] [--dry-run] [--ignore-existing] [--checksum]
                [--destdir=<dir>] [--no-directories] [--source=<source>... | --original]
                [--glob=<pattern> | --format=<format>...] [--concurrent] [--retries=<retries>]
                (<identifier> | --itemlist=<itemlist> | --search=<query>) [<file>...]
    ia download --help

options:
    -h, --help
    -v, --verbose               Turn on verbose output [default: False].
    -q, --silent                Turn off ia's output [default: False].
    -l, --log                   Log download results to file. 
    -d, --dry-run               Print URLs to stdout and exit.
    -i, --ignore-existing       Clobber files already downloaded.
    -C, --checksum              Skip files based on checksum [default: False].
    -R, --retries=<retries>     Set number of retries to <retries> [default: 5]
    -I, --itemlist=<itemlist>   Download items from a specified itemlist.
    -S, --search=<query>        Download items returned from a specified search query.
    -s, --source=<source>...    Only download files matching the given source.
    -o, --original              Only download files with source=original.
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
    -c, --concurrent            Download files concurrently using the Python
                                gevent networking library (gevent must be
                                installed).

"""
from __future__ import print_function
import os
import sys
import logging

from docopt import docopt

from internetarchive import get_item, search_items


def itemlist_ids(itemlist):
    for line in open(itemlist):
        yield line.strip()


def search_ids(query):
    for doc in search_items(query):
        yield doc.get('identifier')

def main(argv):
    args = docopt(__doc__, argv=argv)
    config = {} if not args['--log'] else {'logging': {'level': 'INFO'}}
    retries = int(args['--retries'])

    if args['--itemlist']:
        ids = [x.strip() for x in open(args['--itemlist'])]
        total_ids = len(ids)
    elif args['--search']:
        _search = search_items(args['--search'])
        total_ids = _search.num_found
        ids = search_ids(args['--search'])

    # Download specific files.
    if args['<identifier>']:
        if '/' in args['<identifier>']:
            identifier = args['<identifier>'].split('/')[0]
            files = ['/'.join(args['<identifier>'].split('/')[1:])]
        else:
            identifier = args['<identifier>']
            files = args['<file>']
        total_ids = 1
        ids = [identifier]
    else:
        files = None

    for i, identifier in enumerate(ids):
        if total_ids > 1:
            item_index = '{0}/{1}'.format((i + 1), total_ids)
        else:
            item_index = None
        item = get_item(identifier, config=config)

        # Otherwise, download the entire item.
        if args['--source']:
            ia_source = args['--source']
        elif args['--original']:
            ia_source = ['original']
        else:
            ia_source = None

        errors = item.download(
            files=files,
            concurrent=args['--concurrent'],
            source=ia_source,
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
    if errors:
        #TODO: add option for a summary/report.
        sys.exit(1)
    else:
        sys.exit(0)
