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

"""List files in a given item.

usage:
    ia list [-v] [--glob=<pattern>] [--location] [--format=<format>...]
            [--columns <column1,column2> | --all] <identifier>

options:
    -h, --help
    -v, --verbose               Print column headers. [default: False]
    -a, --all                   List all information available for files.
    -l, --location              Print full URL for each file.
    -c, --columns=<name,size>   List specified file information. [default: name]
    -g, --glob=<pattern>        Only return patterns match the given pattern.
    -f, --format=<format>       Return files matching <format>.
"""
import sys
import csv
from itertools import chain
from fnmatch import fnmatch
import six

from docopt import docopt


def main(argv, session):
    args = docopt(__doc__, argv=argv)
    item = session.get_item(args['<identifier>'])

    files = item.files
    if args.get('--all'):
        columns = list(set(chain.from_iterable(k for k in files)))
    else:
        columns = args['--columns'].split(',')

    # Make "name" the first column always.
    if 'name' in columns:
        columns.remove('name')
        columns.insert(0, 'name')

    dict_writer = csv.DictWriter(sys.stdout, columns, delimiter='\t', lineterminator='\n')

    if args.get('--glob'):
        patterns = args['--glob'].split('|')
        files = [f for f in files if any(fnmatch(f['name'], p) for p in patterns)]
    elif args.get('--format'):
        files = [f.__dict__ for f in item.get_files(formats=args['--format'])]

    output = []
    for f in files:
        file_dict = {}
        for key, val in f.items():
            if key in columns:
                if six.PY2:
                    if isinstance(val, (list, tuple, set)):
                        val = ';'.join(val)
                    val = val.encode('utf-8')
                if key == 'name' and args.get('--location'):
                    file_dict[key] = ('https://archive.org/download/'
                                      '{id}/{f}'.format(id=item.identifier, f=val))
                else:
                    file_dict[key] = val
        output.append(file_dict)

    if args['--verbose']:
        dict_writer.writer.writerow(columns)
    if all(x == {} for x in output):
        sys.exit(1)
    dict_writer.writerows(output)
