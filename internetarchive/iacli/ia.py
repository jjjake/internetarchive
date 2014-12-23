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
def suppress_keyboard_interrupt_message():
    """Register a new excepthook to suppress KeyboardInterrupt
    exception messages, and exit with status code 130.

    """
    old_excepthook = sys.excepthook

    def new_hook(type, value, traceback):
        if type != KeyboardInterrupt:
            old_excepthook(type, value, traceback)
        else:
            sys.exit(130)

    sys.excepthook = new_hook

import sys
suppress_keyboard_interrupt_message()
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
            sys.stderr.write(__doc__.strip() + '\n')
        sys.exit(1)

    # Dynamically import and call subcommand module specified on the
    # command line.
    module = 'internetarchive.iacli.ia_{0}'.format(cmd)
    try:
        globals()['ia_module'] = __import__(module, fromlist=['internetarchive.iacli'])
    except ImportError:
        sys.stderr.write('error: "{0}" is not an `ia` command!\n'.format(cmd))
        sys.exit(127)

    ia_module.main(argv)

if __name__ == '__main__':
    main()
