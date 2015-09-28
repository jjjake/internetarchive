"""Download files from archive.org.

usage:
    ia download [--quiet] [--log] [--dry-run] [--ignore-existing] [--checksum]
                [--destdir=<dir>] [--no-directories] [--source=<source>... | --original]
                [--glob=<pattern> | --format=<format>...] [--concurrent]
                (<identifier> | --itemlist=<itemlist> | --search=<query>) [<file>...]
    ia download --help

options:
    -h, --help
    -q, --quiet                 Turn off ia's output [default: False].
    -l, --log                   Log download results to file. 
    -d, --dry-run               Print URLs to stdout and exit.
    -i, --ignore-existing       Clobber files already downloaded.
    -C, --checksum              Skip files based on checksum [default: False].
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
import os
import sys

from docopt import docopt

from internetarchive import get_item, search_items


def itemlist_ids(itemlist):
    for line in open(itemlist):
        yield line.strip()


def search_ids(query):
    for doc in search_items(query):
        yield doc.get('identifier')


# ia_download()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)
    config = {} if not args['--log'] else {'logging': {'level': 'INFO'}}

    if args['--itemlist']:
        ids = itemlist_ids(args['--itemlist'])
    elif args['--search']:
        ids = search_ids(args['--search'])
    else:
        ids = [args['<identifier>']]

    # Download specific files.
    if args['<identifier>']:
        if '/' in args['<identifier>']:
            identifier = args['<identifier>'].split('/')[0]
            files = [identifier.split('/')[1:]]
        else:
            identifier = args['<identifier>']
            files = args['<file>']
    else:
        files = None

    for identifier in ids:
        item = get_item(identifier, config=config)
        if (args['--quiet'] is False) and (args['--dry-run'] is False):
            verbose = True
        else:
            verbose = False

        if files:
            if verbose:
                sys.stdout.write('{0}:\n'.format(identifier))
            for f in files:
                fname = f.encode('utf-8')
                if args['--no-directories']:
                    path = fname
                else:
                    path = os.path.join(identifier, fname)
                f = item.get_file(fname)
                if not f:
                    sys.stderr.write(' {} doesn\'t exist!\n'.format(fname))
                    continue
                if args['--dry-run']:
                    sys.stdout.write(f.url + '\n')
                else:
                    f.download(path, verbose, args['--ignore-existing'],
                               args['--checksum'], args['--destdir'])
            sys.exit(0)

        # Otherwise, download the entire item.
        if args['--source']:
            ia_source = args['--source']
        elif args['--original']:
            ia_source = ['original']
        else:
            ia_source = None

        item.download(
            concurrent=args['--concurrent'],
            source=ia_source,
            formats=args['--format'],
            glob_pattern=args['--glob'],
            dry_run=args['--dry-run'],
            verbose=verbose,
            ignore_existing=args['--ignore-existing'],
            checksum=args['--checksum'],
            destdir=args['--destdir'],
            no_directory=args['--no-directories'],
        )
    sys.exit(0)
