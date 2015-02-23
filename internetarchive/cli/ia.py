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
from internetarchive.cli import *


# main()
#_________________________________________________________________________________________
def main():
    """This is the CLI driver for ia-wrapper."""
    args = docopt(__doc__, version=__version__, options_first=True)

    # Get subcommand.
    cmd = args['<command>']
    aliases = dict(
        md='metadata',
        up='upload',
        do='download',
        rm='delete',
        se='search',
        ta='tasks',
        ls='list',
    )
    if cmd in aliases:
        cmd = aliases[cmd]

    argv = [cmd] + args['<args>']

    if (cmd == 'help') or (not cmd):
        if not args['<args>']:
            sys.exit(sys.stderr.write(__doc__.strip() + '\n'))
        else:
            sys.exit(call(['ia', args['<args>'][-1], '--help']))

    try:
        ia_module = globals()['ia_{}'.format(cmd)]
    except KeyError:
        sys.stderr.write(__doc__.strip() + '\n\n')
        sys.stderr.write('error: "{0}" is not an `ia` command!\n'.format(cmd))
        sys.exit(127)

    sys.exit(ia_module.main(argv))

if __name__ == '__main__':
    main()
