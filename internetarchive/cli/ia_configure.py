"""Configure 'ia' with your Archive.org credentials.

usage:
    ia configure [--help]

options:
    -h, --help
"""
from __future__ import absolute_import, print_function, unicode_literals
import sys

from docopt import docopt

from internetarchive import configure
from internetarchive.exceptions import AuthenticationError


def main(argv, session):
    docopt(__doc__, argv=argv)
    print("Enter your Archive.org credentials below to configure 'ia'.\n")
    try:
        configure()
    except AuthenticationError as exc:
        print('\nerror: {0}'.format(str(exc)))
        sys.exit(1)
