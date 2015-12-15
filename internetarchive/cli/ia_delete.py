"""Delete files from Archive.org.

usage:
    ia delete <identifier> <file>... [options]...
    ia delete <identifier> [options]...
    ia delete --help

options:
    -h, --help
    -q, --quiet                Print status to stdout.
    -c, --cascade              Delete all derivative files associated with the given file.
    -a, --all                  Delete all files in the given item (Note: Some files, such
                               as <identifier>_meta.xml and <identifier>_files.xml, cannot
                               be deleted)
    -d, --dry-run              Output files to be deleted to stdout, but don't actually
                               delete.
    -g, --glob=<pattern>       Only delete files matching the given pattern.
    -f, --format=<format>...   Only only delete files matching the specified format(s).
"""
from __future__ import absolute_import, print_function, unicode_literals

import sys
from six import text_type

from docopt import docopt, printable_usage
from schema import Schema, SchemaError, Use, Or, And

from internetarchive.cli.argparser import get_xml_text
from internetarchive.utils import validate_ia_identifier


def main(argv, session):
    args = docopt(__doc__, argv=argv)

    # Validation error messages.
    invalid_id_msg = ('<identifier> should be between 3 and 80 characters in length, and '
                      'can only contain alphanumeric characters, underscores ( _ ), or '
                      'dashes ( - )')

    # Validate args.
    s = Schema({
        text_type: Use(lambda x: bool(x)),
        '<file>': list,
        '--format': list,
        '--glob': list,
        'delete': bool,
        '<identifier>': Or(None, And(str, validate_ia_identifier, error=invalid_id_msg)),
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print('{0}\n{1}'.format(str(exc), printable_usage(__doc__)), file=sys.stderr)
        sys.exit(1)

    verbose = True if not args['--quiet'] else False
    item = session.get_item(args['<identifier>'])
    if not item.exists:
        print('{0}: skipping, item does\'t exist.')

    # Files that cannot be deleted via S3.
    no_delete = ['_meta.xml', '_files.xml', '_meta.sqlite']

    if verbose:
        sys.stdout.write('Deleting files from {0}\n'.format(item.identifier))

    if args['--all']:
        files = [f for f in item.iter_files()]
        args['--cacade'] = True
    elif args['--glob']:
        files = item.get_files(glob_pattern=args['--glob'])
    elif args['--format']:
        files = item.get_files(formats=args['--format'])
    else:
        fnames = []
        if args['<file>'] == ['-']:
            fnames = [f.strip().decode('utf-8') for f in sys.stdin]
        else:
            fnames = [f.strip().decode('utf-8') for f in args['<file>']]

        files = [f for f in [item.get_file(f) for f in fnames] if f]

    if not files:
        sys.stderr.write(' warning: no files found, nothing deleted.\n')
        sys.exit(1)

    for f in files:
        if not f:
            if verbose:
                sys.stderr.write(' error: "{0}" does not exist\n'.format(f.name))
            sys.exit(1)
        if any(f.name.endswith(s) for s in no_delete):
            continue
        if args['--dry-run']:
            sys.stdout.write(' will delete: {0}/{1}\n'.format(item.identifier,
                                                              f.name.encode('utf-8')))
            continue
        resp = f.delete(verbose=verbose, cascade_delete=args['--cascade'])
        if resp.status_code != 204:
            msg = get_xml_text(resp.content)
            sys.stderr.write(' error: {0} ({1})\n'.format(msg, resp.status_code))
            sys.exit(1)
