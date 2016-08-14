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

"""
internetarchive.cli.argparser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2016 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from collections import defaultdict
import sys

from six.moves.urllib.parse import parse_qsl


def get_args_dict(args, query_string=False):
    args = [] if not args else args
    metadata = defaultdict(list)
    for md in args:
        if query_string:
            if (':' in md) and ('=' not in md):
                md = md.replace(':', '=')
            for key, value in parse_qsl(md):
                assert value
                metadata[key] = value
        else:
            key, value = md.split(':', 1)
            assert value
            if value not in metadata[key]:
                metadata[key].append(value)

    for key in metadata:
        # Flatten single item lists.
        if len(metadata[key]) <= 1:
            metadata[key] = metadata[key][0]

    return metadata


def convert_str_list_to_unicode(str_list):
    unicode_list = list()
    for x in str_list:
        unicode_list.append(x.decode(sys.getfilesystemencoding()))
    return unicode_list
