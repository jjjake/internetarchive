"""Configure the `ia` CLI and internetarchive Python library.

usage:
    ia configure [--help]

options:
    -h, --help
"""
import sys

from docopt import docopt

from internetarchive import configure
from internetarchive.exceptions import AuthenticationError


# ia_configure()
# ________________________________________________________________________________________
def main(argv, session):
    docopt(__doc__, argv=argv)

    sys.stdout.write(
        'Enter your Archive.org credentials below to configure ia.\n\n')

    try:
        configure()
    except AuthenticationError as exc:
        sys.stdout.write('\n')
        sys.stderr.write('error: {0}\n'.format(str(exc)))
        sys.exit(1)

    sys.exit(0)
