#!/usr/bin/env python
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2019 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A command line interface to Archive.org.

usage:
    ia [--help | --version]
    ia [--config-file FILE] [--log | --debug]
       [--insecure] [--host HOST] <command> [<args>]...

options:
    -h, --help
    -v, --version
    -c, --config-file FILE  Use FILE as config file. (Can also be set with the
                            IA_CONFIG_FILE environment variable. The option takes
                            precedence when both are used.)
    -l, --log               Turn on logging [default: False].
    -d, --debug             Turn on verbose logging [default: False].
    -i, --insecure          Use HTTP for all requests instead of HTTPS [default: false]
    -H, --host HOST         Host to use for requests (doesn't work for requests made to
                            s3.us.archive.org) [default: archive.org]

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
    copy      Copy files in archive.org items.
    move      Move/rename files in archive.org items.
    reviews   Submit/modify reviews for archive.org items.

Documentation for 'ia' is available at:

    https://archive.org/services/docs/api/internetarchive/cli.html

See 'ia help <command>' for help on a specific command.
"""
from __future__ import annotations

import difflib
import errno
import os
import sys

from docopt import docopt, printable_usage

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points  # type: ignore[import]
else:
    from importlib.metadata import entry_points
from schema import Or, Schema, SchemaError  # type: ignore[import]

from internetarchive import __version__
from internetarchive.api import get_session
from internetarchive.utils import suppress_keyboard_interrupt_message

suppress_keyboard_interrupt_message()


cmd_aliases = {
    'co': 'configure',
    'md': 'metadata',
    'up': 'upload',
    'do': 'download',
    'rm': 'delete',
    'se': 'search',
    'ta': 'tasks',
    'ls': 'list',
    'cp': 'copy',
    'mv': 'move',
    're': 'reviews',
}


def load_ia_module(cmd: str):
    """Dynamically import ia module."""
    try:
        if cmd in list(cmd_aliases.keys()) + list(cmd_aliases.values()):
            _module = f'internetarchive.cli.ia_{cmd}'
            return __import__(_module, fromlist=['internetarchive.cli'])
        else:
            _module = f'ia_{cmd}'
            for ep in entry_points(group='internetarchive.cli.plugins'):
                if ep.name == _module:
                    return ep.load()
            raise ImportError
    except (ImportError):
        print(f"error: '{cmd}' is not an ia command! See 'ia help'",
              file=sys.stderr)
        matches = '\t'.join(difflib.get_close_matches(cmd, cmd_aliases.values()))
        if matches:
            print(f'\nDid you mean one of these?\n\t{matches}', file=sys.stderr)
        sys.exit(127)


def main() -> None:
    """This is the CLI driver for ia-wrapper."""
    args = docopt(__doc__, version=__version__, options_first=True)

    # Validate args.
    s = Schema({
        str: bool,
        '--config-file': Or(None, str),
        '--host': Or(None, str),
        '<args>': list,
        '<command>': Or(str, lambda _: 'help'),
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print(f'{exc}\n{printable_usage(__doc__)}', file=sys.stderr)
        sys.exit(1)

    # Get subcommand.
    cmd = args['<command>']
    if cmd in cmd_aliases:
        cmd = cmd_aliases[cmd]

    if (cmd == 'help') or (not cmd):
        if not args['<args>']:
            sys.exit(print(__doc__.strip(), file=sys.stderr))
        else:
            ia_module = load_ia_module(args['<args>'][0])
            sys.exit(print(ia_module.__doc__.strip(), file=sys.stderr))

    if cmd != 'configure' and args['--config-file']:
        if not os.path.isfile(args['--config-file']):
            print(f'--config-file should be a readable file.\n{printable_usage(__doc__)}',
                  file=sys.stderr)
            sys.exit(1)

    argv = [cmd] + args['<args>']

    config: dict[str, dict] = {}
    if args['--log']:
        config['logging'] = {'level': 'INFO'}
    elif args['--debug']:
        config['logging'] = {'level': 'DEBUG'}

    if args['--insecure']:
        config['general'] = {'secure': False}
    if args['--host']:
        if config.get('general'):
            config['general']['host'] = args['--host']
        else:
            config['general'] = {'host': args['--host']}

    session = get_session(config_file=args['--config-file'],
                          config=config,
                          debug=args['--debug'])

    ia_module = load_ia_module(cmd)
    try:
        sys.exit(ia_module.main(argv, session))
    except OSError as e:
        # Handle Broken Pipe errors.
        if e.errno == errno.EPIPE:
            sys.stderr.close()
            sys.stdout.close()
            sys.exit(0)
        else:
            raise


if __name__ == '__main__':
    main()
