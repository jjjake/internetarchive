# -*- coding: utf-8 -*-
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

"""Submit and modify reviews for archive.org items.

For more information on how to use this command, refer to the
Reviews API documentation::

    https://archive.org/services/docs/api/reviews.html

usage:
    ia reviews <identifier> --title=<title> --body=<body> [--stars=<stars>]
    ia reviews --help

options:
    -h, --help
    -t, --title=<title>    The title of your review.
    -b, --body=<body>      The body of your review.
    -s, --stars=<stars>    The number of stars for your review.

examples:
    ia reviews nasa
"""
from __future__ import absolute_import, print_function
import sys

from docopt import docopt


def main(argv, session):
    args = docopt(__doc__, argv=argv)

    item = session.get_item(args['<identifier>'])
    r = item.review(args['--title'], args['--body'], args['--stars'])
    j = r.json()
    if j.get('success') or 'no change detected' in j.get('error', '').lower():
        task_id = j.get('value', dict()).get('task_id')
        if task_id:
            print('{} - success: https://catalogd.archive.org/log/{}'.format(
                item.identifier, task_id))
        else:
            print('{} - warning: no changes detected!'.format(item.identifier))
        sys.exit(0)
    else:
        print('{} - error: {}'.format(item.identifier, j.get('error')))
        sys.exit(1)
