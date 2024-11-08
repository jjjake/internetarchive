#!/usr/bin/env python
"""
ia.py

The internetarchive module is a Python/CLI interface to Archive.org.
"""

# Copyright (C) 2012-2024 Internet Archive
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

import argparse
import signal
import sys

from internetarchive import __version__, get_session
from internetarchive.cli import (
    ia_configure,
    ia_copy,
    ia_delete,
    ia_download,
    ia_list,
    ia_metadata,
    ia_move,
    ia_reviews,
    ia_search,
    ia_tasks,
    ia_upload,
)
from internetarchive.cli.cli_utils import exit_on_signal

# Handle broken pipe
try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except AttributeError:
    # Non-unix support
    pass

# Handle <Ctrl-C>
signal.signal(signal.SIGINT, exit_on_signal)


def validate_config_path(path):
    """
    Validate the path to the configuration file.

    Returns:
        str: Validated path to the configuration file.
    """
    if "configure" not in sys.argv:  # Support for adding config to specific file
        file_check = argparse.FileType("r")
        file_check(path)
    return path


def main():
    """
    Main entry point for the CLI.
    """
    parser = argparse.ArgumentParser(
            description="A command line interface to Archive.org.",
            epilog=("Documentation for 'ia' is available at:\n\n\t"
                    "https://archive.org/developers/internetarchive/cli.html\n\n"
                    "See 'ia {command} --help' for help on a specific command."),
            formatter_class=argparse.RawTextHelpFormatter)  # support for \n in epilog

    parser.add_argument("-v", "--version",
                        action="version",
                        version=__version__)
    parser.add_argument("-c", "--config-file",
                        action="store",
                        type=validate_config_path,
                        metavar="FILE",
                        help="path to configuration file")
    parser.add_argument("-l", "--log",
                        action="store_true",
                        default=False,
                        help="enable logging")
    parser.add_argument("-d", "--debug",
                        action="store_true",
                        help="enable debugging")
    parser.add_argument("-i", "--insecure",
                        action="store_true",
                        help="allow insecure connections")
    parser.add_argument("-H", "--host",
                        action="store",
                        help=("host to connect to "
                              "(doesn't work for requests made to s3.us.archive.org)"))

    subparsers = parser.add_subparsers(title="commands",
                                       dest="command",
                                       metavar="{command}")

    # Add subcommand parsers
    ia_configure.setup(subparsers)
    ia_copy.setup(subparsers)
    ia_delete.setup(subparsers)
    ia_download.setup(subparsers)
    ia_list.setup(subparsers)
    ia_metadata.setup(subparsers)
    ia_move.setup(subparsers)
    ia_reviews.setup(subparsers)
    ia_search.setup(subparsers)
    ia_tasks.setup(subparsers)
    ia_upload.setup(subparsers)

    # Suppress help for alias subcommands
    args = parser.parse_args()

    config: dict[str, dict] = {}
    if args.log:
        config["logging"] = {"level": "INFO"}
    elif args.debug:
        config["logging"] = {"level": "DEBUG"}

    if args.insecure:
        config["general"] = {"secure": False}
    if args.host:
        if config.get("general"):
            config["general"]["host"] = args["--host"]
        else:
            config["general"] = {"host": args["--host"]}

    args.session = get_session(config_file=args.config_file,
                               config=config,
                               debug=args.debug)

    # Check if any arguments were provided
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
