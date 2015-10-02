#!/usr/bin/env python
"""A command line interface to Archive.org.

usage:
    ia [--help | --version]
    ia [--config-file FILE] [--log] <command> [<args>]...

options:
    -h, --help
    -v, --version
    -c, --config-file FILE  Use FILE as config file.
    -l, --log               Turn on logging [default: False].

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
import os
from subprocess import call

from docopt import docopt, printable_usage
from schema import Schema, Use, Or, And, SchemaError

from internetarchive import __version__
from internetarchive import get_session
from internetarchive.config import get_config
from internetarchive.cli import *


def main():
    """This is the CLI driver for ia-wrapper."""
    args = docopt(__doc__, version=__version__, options_first=True)

    # Validate args.
    s = Schema({str: bool,
        '--config-file': Or(None, lambda f: os.path.exists(f),
            error='--config-file should be a readable file.'),
        '<args>': list,
        '<command>': str,
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        sys.stderr.write('{0}\n{1}\n'.format(str(exc), printable_usage(__doc__)))
        sys.exit(1)

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

    if (cmd == 'help') or (not cmd):
        if not args['<args>']:
            sys.exit(sys.stderr.write(__doc__.strip() + '\n'))
        else:
            sys.exit(call(['ia', args['<args>'][-1], '--help']))

    argv = [cmd] + args['<args>']


    try:
        ia_module = globals()['ia_{0}'.format(cmd)]
    except KeyError:
        sys.stderr.write(__doc__.strip() + '\n\n')
        sys.stderr.write('error: "{0}" is not an `ia` command!\n'.format(cmd))
        sys.exit(127)

    config = {'logging': {'level': 'INFO'}} if args['--log'] else None
    session = get_session(config_file=args['--config-file'], config=config)
    sys.exit(ia_module.main(argv, session))

if __name__ == '__main__':
    main()
