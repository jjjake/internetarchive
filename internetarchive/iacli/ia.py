#!/usr/bin/env python
"""A command line interface for Archive.org.

usage:
    ia [--debug | --help | --version] [<command>] [<args>...]

options:
    -h, --help
    -v, --version
    -d, --debug  [default: True]

commands:
    help      Retrieve help for subcommands.
    configure Configure `ia`.
    metadata  Retrieve and modify metadata for items on Archive.org.
    upload    Upload items to Archive.org.
    download  Download files from Archive.org.
    delete    Delete files from Archive.org.
    search    Search Archive.org.
    mine      Download item metadata from Archive.org concurrently.
    tasks     Retrieve information about your Archive.org catalog tasks.
    list      List files in a given item.

See 'ia help <command>' for more information on a specific command.

"""
import sys
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
        md='metadata',
        up='upload',
        do='download',
        rm='delete',
        se='search',
        mi='mine',
        ta='tasks',
        ls='list',
    )
    if cmd in aliases:
        cmd = aliases[cmd]

    argv = [cmd] + args['<args>']

    if cmd == 'help' or not cmd:
        if not args['<args>']:
            call(['ia', '--help'])
        else:
            call(['ia', args['<args>'][0], '--help'])
        sys.exit(0)

    # Dynamically import and call subcommand module specified on the
    # command line.
    module = 'internetarchive.iacli.ia_{0}'.format(cmd)
    try:
        globals()['ia_module'] = __import__(module, fromlist=['internetarchive.iacli'])
    except ImportError:
        sys.stderr.write('error: "{0}" is not an `ia` command!\n'.format(cmd))
        sys.exit(1)
    try:
        ia_module.main(argv)
    except KeyboardInterrupt:
        sys.exit(1)

if __name__ == '__main__':
    main()
