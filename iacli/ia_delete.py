"""Delete files from Archive.org via the Internet Archive's S3 like server API. 

IA-S3 Documentation: https://archive.org/help/abouts3.txt

usage: 
    ia delete [--verbose] [--debug] <identifier> <file>...
    ia delete --help

options:
    -h, --help
    -v, --verbose                  Print upload status to stdout.

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

    if verbose:
        stdout.write('Deleting files from {0}\n'.format(item.identifier))

    for f in args['<file>']:
        file = item.file(f)
        if not file:
            if verbose:
                stderr.write(' error: "{0}" does not exist\n'.format(f))
            exit(1)
        resp = file.delete(verbose=args['--verbose'])
        if resp.status_code != 204:
            error = parseString(resp.content)
            msg = get_xml_text(error.getElementsByTagName('Message'))
            stderr.write(' error: {0} ({1})\n'.format(msg, resp.status_code))
            exit(1)
