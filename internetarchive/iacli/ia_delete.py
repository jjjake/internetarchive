"""Delete files from Archive.org via the Internet Archive's S3 like server API.

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage:
    ia delete [--quiet] [--debug] [--dry-run] [--cascade] <identifier> <file>...
    ia delete [--quiet] [--debug] [--dry-run] --all <identifier>
    ia delete [--quiet] [--debug] [--dry-run] --glob=<pattern> <identifier>
    ia delete --help

options:
    -h, --help
    -q, --quiet            Print status to stdout. 
    -c, --cascade          Delete all derivative files associated with the given file.
    -a, --all              Delete all files in the given item (Note: Some files, such
                           as <identifier>_meta.xml and <identifier>_files.xml, cannot
                           be deleted)
    -d, --dry-run          Output files to be deleted to stdout, but don't actually delete.
    -g, --glob=<pattern>   Only return patterns match the given pattern.

"""
import sys
from xml.dom.minidom import parseString
from fnmatch import fnmatch

from docopt import docopt

from internetarchive import get_item
from internetarchive.iacli.argparser import get_xml_text


# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)
    verbose = True if not args['--quiet'] else False
    item = get_item(args['<identifier>'])

    # Files that cannot be deleted via S3.
    no_delete = ['_meta.xml', '_files.xml', '_meta.sqlite']

    if verbose:
        sys.stdout.write('Deleting files from {0}\n'.format(item.identifier))

    if args['--all']:
        files = [f for f in item.iter_files()]
        args['--cacade'] = True
    elif args['--glob']:
        files = item.get_files(glob_pattern=args['--glob'])
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
            error = parseString(resp.content)
            msg = get_xml_text(error.getElementsByTagName('Message'))
            sys.stderr.write(' error: {0} ({1})\n'.format(msg, resp.status_code))
            sys.exit(1)
