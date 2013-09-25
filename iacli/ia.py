#!/usr/bin/env python
"""A command line interface for Archive.org.

usage: 
    ia [--version|--help|--debug] <command> [<args>...]

options:
    --version  
    -h, --help  
    -d, --debug  [default: True]

commands:
    configure Configure `ia`.
    metadata  Retrieve and modify metadata for items on archive.org
    upload    Upload items to archive.org
    download  Download files from archive.org
    search    Search archive.org
    mine      Download item metadata concurrently.
    catalog   Retrieve information about your catalog tasks

See 'ia <command> --help' for more information on a specific command.

"""
from sys import exit
from subprocess import call

from docopt import docopt

from internetarchive import __version__



# main()
#_________________________________________________________________________________________
def main():
    """This script is the CLI driver for ia-wrapper. It dynamically
    imports and calls the subcommand specified on the command line. It 
    depends on the ``internetarchive`` and ``iacli`` packages.

    Subcommands can be arbitrarily added to the ``iacli`` package as 
    modules, and can be dynamically executed via this script, ``ia``.

    """
    args = docopt(__doc__, version=__version__, options_first=True)

    # Get subcommand.
    cmd = args['<command>']
    aliases = dict(
            md = 'metadata',
            up = 'upload',
            ca = 'catalog',
            se = 'search',
            mi = 'mine',
            do = 'download',
    )
    if cmd in aliases:
        cmd = aliases[cmd]

    argv = [cmd] + args['<args>']
    
    # Dynamically import and call subcommand module specified on the 
    # command line.
    module = 'iacli.ia_{0}'.format(cmd) 
    globals()['ia_module'] = __import__(module, fromlist=['iacli'])

    # Exit with ``ia <command> --help`` if anything goes wrong.
    try:
        ia_module.main(argv)
    except Exception, exception:
        if not args.get('--debug'):
            call(['ia', cmd, '--help'])
            exit(1)
        raise exception


if __name__ == '__main__':
    main()
