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

"""Configure 'ia' with your Archive.org credentials.

usage:
    ia configure [--help]

options:
    -h, --help
"""
from __future__ import absolute_import, print_function, unicode_literals
import sys

from docopt import docopt

from internetarchive import configure
from internetarchive.exceptions import AuthenticationError


def main(argv, session):
    docopt(__doc__, argv=argv)
    print("Enter your Archive.org credentials below to configure 'ia'.\n")
    try:
        configure(config_file=session.config_file)
    except AuthenticationError as exc:
        print('\nerror: {0}'.format(str(exc)))
        sys.exit(1)
