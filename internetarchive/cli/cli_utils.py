"""
interneratchive.cli.cli_utils

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

from __future__ import annotations

import argparse
import os
import signal
import sys
from collections import defaultdict
from typing import Mapping
from urllib.parse import parse_qsl

from internetarchive.utils import InvalidIdentifierException, validate_s3_identifier


def get_args_dict(args: list[str],
                  query_string: bool = False,
                  header: bool = False) -> dict:
    args = args or []
    if not isinstance(args, list):
        args = [args]
    metadata: dict[str, list | str] = defaultdict(list)
    for md in args:
        if query_string:
            if (":" in md) and ("=" not in md):
                md = md.replace(":", "=").replace(";", "&")
            for key, value in parse_qsl(md):
                assert value
                metadata[key] = value
        else:
            key, value = md.split(":", 1)
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
        target = "/".join(key.split("/")[:-1])
        field = key.split("/")[-1]
        if not changes[target]:
            changes[target] = {field: value}
        else:
            changes[target][field] = value
    return changes


def convert_str_list_to_unicode(str_list: list[bytes]):
    encoding = sys.getfilesystemencoding()
    return [b.decode(encoding) for b in str_list]


def validate_identifier(identifier):
    try:
        validate_s3_identifier(identifier)
    except InvalidIdentifierException as e:
        raise argparse.ArgumentTypeError(str(e))
    return identifier


def prepare_args_dict(args, parser, arg_type="metadata", many=False, query_string=False):
    if not args:
        return {}
    try:
        if many:
            return get_args_dict_many_write([item for sublist in args for item in sublist])
        else:
            if isinstance(args[0], list):
                return get_args_dict([item for sublist in args for item in sublist],
                                     query_string=query_string)
            else:
                return get_args_dict(args, query_string=query_string)
    except ValueError as e:
        parser.error(f"--{arg_type} must be formatted as --{arg_type}='key:value'")


def validate_dir_path(path):
    """
    Check if the given path is a directory that exists.

    Args:
        path (str): The path to check.

    Returns:
        str: The validated directory path.

    Raises:
        argparse.ArgumentTypeError: If the path is not a valid directory.
    """
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"'{path}' is not a valid directory")


def exit_on_signal(sig, frame):
    """
    Exit the program cleanly upon receiving a specified signal.

    This function is designed to be used as a signal handler. When a signal
    (such as SIGINT or SIGPIPE) is received, it exits the program with an
    exit code of 128 plus the signal number. This convention helps to
    distinguish between regular exit codes and those caused by signals.
    """
    exit_code = 128 + sig
    sys.exit(exit_code)
