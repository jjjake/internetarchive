"""Download files from archive.org.

usage:
    ia download [--quiet] [--dry-run] [--ignore-existing] [--checksum]
                [--source=<source>... | --original]
                [--glob=<pattern> | --format=<format>...] [--concurrent] <identifier>
                [<file>...]
    ia download --help

options:
    -h, --help
    -q, --quiet               Turn off ia's output [default: False].
    -d, --dry-run             Print URLs to stdout and exit.
    -i, --ignore-existing     Clobber files already downloaded.
    -C, --checksum            Skip files based on checksum [default: False].
    -s, --source=<source>...  Only download files matching the given source.
    -o, --original            Only download files with source=original.
    -g, --glob=<pattern>      Only download files whose filename matches the
                              given glob pattern.
    -f, --format=<format>...  Only download files of the specified format(s).
                              You can use the following command to retrieve
                              a list of file formats contained within a given
                              item:

                                  ia metadata --formats <identifier>

    -c, --concurrent          Download files concurrently using the Python
                              gevent networking library (gevent must be
                              installed).

"""
import os
import sys

from docopt import docopt

from internetarchive import get_item


# ia_download()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    # Download specific files.
    if '/' in args['<identifier>']:
        identifier = args['<identifier>'].split('/')[0]
        files = [identifier.split('/')[1:]]
    else:
        identifier = args['<identifier>']
        files = args['<file>']

    item = get_item(identifier)
    verbose = True if args['--quiet'] is False else False

    if files:
        if verbose:
            sys.stdout.write('{0}:\n'.format(identifier))
        for f in files:
            fname = f.encode('utf-8')
            path = os.path.join(identifier, fname)
            f = item.get_file(fname)
            if args['--dry-run']:
                sys.stdout.write(f.url + '\n')
            else:
                f.download(path, verbose, args['--ignore-existing'], args['--checksum'])
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
    )
    sys.exit(0)
