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
    ia reviews <identifier>
    ia reviews <identifier> --delete [--username=<username> | --screenname=<screenname>
                                      | --itemname=<itemname>]
    ia reviews <identifier> --title=<title> --body=<body> [--stars=<stars>]
    ia reviews --help

options:
    -h, --help
    -t, --title=<title>             The title of your review.
    -b, --body=<body>               The body of your review.
    -s, --stars=<stars>             The number of stars for your review.
    -d, --delete                    Delete your review. [default: False]
    -u, --username=<username>       Delete reviews for a specific user
                                    given username (must be used with --delete).
    -S, --screenname=<screenname>   Delete reviews for a specific user
                                    given screenname (must be used with --delete).
    -I, --itemname=<itemname>       Delete reviews for a specific user
                                    given itemname (must be used with --delete).

examples:
    ia reviews nasa
"""
import sys

from docopt import docopt
from requests.exceptions import HTTPError

from internetarchive import ArchiveSession


def main(argv, session: ArchiveSession) -> None:
    args = docopt(__doc__, argv=argv)

    item = session.get_item(args['<identifier>'])
    if args['--delete']:
        r = item.delete_review(username=args['--username'],
                               screenname=args['--screenname'],
                               itemname=args['--itemname'])
    elif not args['--body']:
        try:
            r = item.get_review()
            print(r.text)
            sys.exit(0)
        except HTTPError as exc:
            if exc.response.status_code == 404:  # type: ignore
                sys.exit(0)
            else:
                raise exc
    else:
        r = item.review(args['--title'], args['--body'], args['--stars'])
    j = r.json()
    if j.get('success') or 'no change detected' in j.get('error', '').lower():
        task_id = j.get('value', {}).get('task_id')
        if task_id:
            print(f'{item.identifier} - success: https://catalogd.archive.org/log/{task_id}',
                  file=sys.stderr)
        else:
            print(f'{item.identifier} - warning: no changes detected!', file=sys.stderr)
        sys.exit(0)
    else:
        print(f'{item.identifier} - error: {j.get("error")}', file=sys.stderr)
        sys.exit(1)
