#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2016 Internet Archive
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
    ia [--config-file FILE] [--log | --debug] [--insecure] <command> [<args>]...

options:
    -h, --help
    -v, --version
    -c, --config-file FILE  Use FILE as config file.
    -l, --log               Turn on logging [default: False].
    -d, --debug             Turn on verbose logging [default: False].
    -i, --insecure          Use HTTP for all requests instead of HTTPS [default: false]

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

Documentation for 'ia' is available at:

    https://internetarchive.readthedocs.io/en/latest/cli.html

See 'ia help <command>' for help on a specific command.
"""
from __future__ import absolute_import, unicode_literals, print_function

import sys
import os
import difflib
import errno
from pkg_resources import iter_entry_points, DistributionNotFound

from docopt import docopt, printable_usage
from schema import Schema, Or, SchemaError
import six

from internetarchive import __version__
from internetarchive.api import get_session
from internetarchive.utils import suppress_keyboard_interrupt_message
suppress_keyboard_interrupt_message()


cmd_aliases = dict(
    co='configure',
    md='metadata',
    up='upload',
    do='download',
    rm='delete',
    se='search',
    ta='tasks',
    ls='list',
    cp='copy',
    mv='move',
)


def load_ia_module(cmd):
    """Dynamically import ia module."""
    try:
        if cmd in list(cmd_aliases.keys()) + list(cmd_aliases.values()):
            _module = 'internetarchive.cli.ia_{0}'.format(cmd)
            return __import__(_module, fromlist=['internetarchive.cli'])
        else:
            _module = 'ia_{0}'.format(cmd)
            for ep in iter_entry_points('internetarchive.cli.plugins'):
                if ep.name == _module:
                    return ep.load()
            raise ImportError
    except (ImportError, DistributionNotFound):
        print("error: '{0}' is not an ia command! See 'ia help'".format(cmd),
              file=sys.stderr)
        matches = '\t'.join(difflib.get_close_matches(cmd, cmd_aliases.values()))
        if matches:
            print('\nDid you mean one of these?\n\t{0}'.format(matches))
        sys.exit(127)


def main():
    """This is the CLI driver for ia-wrapper."""
    args = docopt(__doc__, version=__version__, options_first=True)

    # Validate args.
    s = Schema({
        six.text_type: bool,
        '--config-file': Or(None, str),
        '<args>': list,
        '<command>': Or(str, lambda _: 'help'),
    })
    try:
        args = s.validate(args)
    except SchemaError as exc:
        print('{0}\n{1}'.format(str(exc), printable_usage(__doc__)), file=sys.stderr)
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
            print('--config-file should be a readable file.\n{0}'.format(
                printable_usage(__doc__)), file=sys.stderr)
            sys.exit(1)

    argv = [cmd] + args['<args>']

    config = dict()
    if args['--log']:
        config['logging'] = {'level': 'INFO'}
    elif args['--debug']:
        config['logging'] = {'level': 'DEBUG'}

    if args['--insecure']:
        config['general'] = dict(secure=False)

    session = get_session(config_file=args['--config-file'],
                          config=config,
                          debug=args['--debug'])

    ia_module = load_ia_module(cmd)
    try:
        sys.exit(ia_module.main(argv, session))
    except IOError as e:
        # Handle Broken Pipe errors.
        if e.errno == errno.EPIPE:
            sys.stderr.close()
            sys.stdout.close()
            sys.exit(0)
        else:
            raise

if __name__ == '__main__':
    main()
