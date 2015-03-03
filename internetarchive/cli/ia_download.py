"""Download files from archive.org.

usage:
    ia download <identifier> [<file>]... [options]...
    ia download --help

options:
    -h, --help
    -q, --quiet               Turn off ia's output. [default: False]
    -d, --dry-run             Print URLs to stdout and exit.
    -i, --clobber             Clobber files already downloaded.
    -C, --checksum            Skip files already downloaded based on checksum.
                              [default: False]
    -s, --source=<source>...  Only download files matching the given source.
    -g, --glob=<pattern>      Only download files whose filename matches the given glob
                              pattern.
    -f, --format=<format>...  Only download files of the specified format(s).
    --no-directories          Download files into working directory. Do not create item
                              directories.
    --destdir=<dir>           The destination directory to download files and item
                              directories to.

"""
import os
import sys

from docopt import docopt, printable_usage
from schema import Schema, Use, Or, And, SchemaError

from internetarchive import download


# ia_download()
# ________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    valid_sources = ['original', 'derivative', 'metadata']
    s = Schema({str: Use(bool),
        '--destdir': Or([], And(Use(lambda d: d[0]), lambda d: os.path.exists(d)),
            error='--destdir must be a valid path to a directory.'),
        '--format': list,
        '--glob': Use(lambda l: l[0] if l else None),
        '--source': And(list,
            lambda l: all(s in valid_sources for s in l) if l else list,
            error='--source must be "original", "derivative", or "metadata".'),
        '<file>': list,
        '<identifier>': str,
    })

    try:
        args = s.validate(args)
    except SchemaError as exc:
        sys.stderr.write('{0}\n{1}\n'.format(
            str(exc), printable_usage(__doc__)))
        sys.exit(1)

    verbose = False if args['--quiet'] or args['--dry-run'] else True
    no_clobber = True if not args['--clobber'] and not args['--checksum'] else False
    responses = download(
        args['<identifier>'],
        files=args['<file>'],
        source=args['--source'],
        formats=args['--format'],
        glob_pattern=args['--glob'],
        dry_run=args['--dry-run'],
        verbose=verbose,
        clobber=args['--clobber'],
        no_clobber=no_clobber,
        checksum=args['--checksum'],
        destdir=args['--destdir'],
        no_directory=args['--no-directories'],
    )
