"""Download files from archive.org.

usage: 
    ia download [--help] <identifier> [<file>...] [options...]  

options:
    -h, --help  
    --version  
    -i, --ignore-existing      Clobber files already downloaded.
    -s, --source=<source>...   Only Download files matching given sources.
    -o, --original             Download only files with source=original.
    -g, --glob=<pattern>       Only download files whose filename matches the 
                               given glob pattern.
    -f, --format=<format>...   Only download files of the specified format(s).
                               You can use the following command to retrieve
                               a list of file formats contained within a given 
                               item:
                                
                                   ia metadata --formats <identifier>

    -c, --concurrent           Download files concurrently using the Python 
                               gevent networking library.

"""
from docopt import docopt
import sys
import os

import internetarchive



# ia_download()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    if '/' in args['<identifier>']:
        identifier = args['<identifier>'].split('/')[0]
    else:
        identifier = args['<identifier>']
    item = internetarchive.Item(identifier)

    if '/' in args['<identifier>'] or args['<file>']:
        if not args['<file>']:
            fname = args['<identifier>'].split('/')[-1]
            files = [fname]
        else:
            files = args['<file>']
        for f in files:
            fname = f.encode('utf-8')
            path = os.path.join(identifier, fname)
            sys.stdout.write('downloading: {0}\n'.format(fname))
            f = item.file(fname)
            f.download(file_path=path, ignore_existing=args['--ignore-existing'])
        sys.exit(0)

    if args['--format']:
        formats = args['--format']
    else:
        formats = None

    if args['--glob']:
        glob = args['--glob'][0]
    else:
        glob = None

    if args['--source']:
        ia_source = args['--source']
    elif args['--original']:
        ia_source = ['original']
    else:
        ia_source = None

    item.download(formats=formats, source=ia_source, concurrent=args['--concurrent'], 
                  glob_pattern=glob, ignore_existing=args['--ignore-existing'])
    sys.exit(0)
