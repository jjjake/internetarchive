"""Delete files from Archive.org via the Internet Archive's S3 like server API. 

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage: 
    ia delete [--verbose] [--debug] [--cascade] <identifier> <file>...
    ia delete [--verbose] [--debug] --all <identifier>
    ia delete --help

options:
    -h, --help
    -v, --verbose  Print status to stdout.
    -c, --cascade  Delete all derivative files associated with the given file.
    -a, --all      Delete all files in the given item (Note: Some files, such 
                   as <identifier>_meta.xml and <identifier>_files.xml, cannot 
                   be deleted)

"""
from sys import stdout, stderr, exit
from xml.dom.minidom import parseString

from docopt import docopt

from internetarchive import Item
from iacli.argparser import get_xml_text



# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)
    verbose = args['--verbose']
    item = Item(args['<identifier>'])

    # Files that cannot be deleted via S3.
    no_delete = ['_meta.xml', '_files.xml', '_meta.sqlite']

    if verbose:
        stdout.write('Deleting files from {0}\n'.format(item.identifier))

    if args['--all']:
        files = [f for f in item.files()]
        args['--cacade'] = True
    else:
        files = [item.file(f) for f in args['<file>']]

    for f in files:
        if not f:
            if verbose:
                stderr.write(' error: "{0}" does not exist\n'.format(f.name))
            exit(1)
        if any(f.name.endswith(s) for s in no_delete):
            continue
        resp = f.delete(verbose=args['--verbose'], cascade_delete=args['--cascade'])
        if resp.status_code != 204:
            error = parseString(resp.content)
            msg = get_xml_text(error.getElementsByTagName('Message'))
            stderr.write(' error: {0} ({1})\n'.format(msg, resp.status_code))
            exit(1)
