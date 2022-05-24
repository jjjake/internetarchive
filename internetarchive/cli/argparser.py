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

"""
internetarchive.cli.argparser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from typing import Mapping
from urllib.parse import parse_qsl


def get_args_dict(args: list[str], query_string: bool = False, header: bool = False) -> dict:
    args = args or []
    metadata: dict[str, list | str] = defaultdict(list)
    for md in args:
        if query_string:
            if (':' in md) and ('=' not in md):
                md = md.replace(':', '=').replace(';', '&')
            for key, value in parse_qsl(md):
                assert value
                metadata[key] = value
        else:
            key, value = md.split(':', 1)
            assert value
            if value not in metadata[key]:
                metadata[key].append(value)  # type: ignore

    for key in metadata:
        # Flatten single item lists.
        if len(metadata[key]) <= 1:
            metadata[key] = metadata[key][0]

    return metadata


def get_args_header_dict(args: list[str]) -> dict:
    h = get_args_dict(args)
    return {k: v.strip() for k, v in h.items()}


def get_args_dict_many_write(metadata: Mapping):
    changes: dict[str, dict] = defaultdict(dict)
    for key, value in metadata.items():
        target = '/'.join(key.split('/')[:-1])
        field = key.split('/')[-1]
        if not changes[target]:
            changes[target] = {field: value}
        else:
            changes[target][field] = value
    return changes


def convert_str_list_to_unicode(str_list: list[bytes]):
    encoding = sys.getfilesystemencoding()
    return [b.decode(encoding) for b in str_list]
