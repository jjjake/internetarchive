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
import json
import os
import signal
import sys
from collections import defaultdict
from collections.abc import Iterable
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

    for key in metadata:  # noqa: PLC0206
        # Flatten single item lists.
        if len(metadata[key]) <= 1:
            metadata[key] = metadata[key][0]

    return metadata


def convert_str_list_to_unicode(str_list: list[bytes]):
    encoding = sys.getfilesystemencoding()
    return [b.decode(encoding) for b in str_list]


def validate_identifier(identifier):
    try:
        validate_s3_identifier(identifier)
    except InvalidIdentifierException as e:
        raise argparse.ArgumentTypeError(str(e))
    return identifier


def flatten_list(lst):
    """Flatten a list if it contains lists."""
    result = []
    for item in lst:
        if isinstance(item, Iterable) and not isinstance(item, str):
            result.extend(flatten_list(item))  # Recursively flatten
        else:
            result.append(item)  # Just append the item if it's not a list
    return result


class FlattenListAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        # Flatten the list of values (if nested)
        flattened = flatten_list(values)
        # Initialize the attribute if it doesn't exist yet
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, [])
        # Append the flattened list to the existing attribute
        getattr(namespace, self.dest).extend(flattened)


class PostDataAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        current_value = getattr(namespace, self.dest, None)

        # Split values into individual JSON objects (if needed) and parse them
        all_values = []
        for value in values:
            try:
                obj = json.loads(value)
                all_values.append(obj)
            except json.JSONDecodeError as e:
                parser.error(f"Invalid JSON format for post data: {value}")

        # If there is no current value (first argument), initialize it as an object or list
        if current_value is None:
            # If there's only one value, don't wrap it in a list
            if len(all_values) == 1:
                post_data = all_values[0]
            else:
                post_data = all_values
        elif isinstance(current_value, list):
            # If it's already a list, append the new values to it
            post_data = current_value + all_values
        else:
            # If it's a single object (first argument), convert it into a list and append new data
            post_data = [current_value] + all_values

        # Set the final value back to the namespace
        setattr(namespace, self.dest, post_data)


class QueryStringAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        # Initialize the destination as an empty dictionary if it doesn't exist
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, {})

        for sublist in values:
            if "=" not in sublist and ":" in sublist:
                sublist = sublist.replace(":", "=", 1)
            key_value_pairs = parse_qsl(sublist)

            if sublist and not key_value_pairs:
                parser.error(f"{option_string} must be formatted as 'key=value' "
                              "or 'key:value'")

            for key, value in key_value_pairs:
                current_dict = getattr(namespace, self.dest)
                if key in current_dict:
                    current_dict[key].append(value)
                else:
                    current_dict[key] = [value]

        current_dict = getattr(namespace, self.dest)
        for key, value in current_dict.items():
            if len(value) == 1:
                current_dict[key] = value[0]


class MetadataAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        # Initialize the destination as an empty dictionary if it doesn't exist
        if getattr(namespace, self.dest, None) is None:
            setattr(namespace, self.dest, {})

        for sublist in values:
            if ":" not in sublist and "=" in sublist:
                sublist = sublist.replace("=", ":", 1)
            try:
                key, value = sublist.split(":", 1)
            except ValueError:
                parser.error(f"{option_string} must be formatted as 'KEY:VALUE'")

            current_dict = getattr(namespace, self.dest)
            if key in current_dict:
                if not isinstance(current_dict[key], list):
                    current_dict[key] = [current_dict[key]]
                current_dict[key].append(value)
            else:
                current_dict[key] = value


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
