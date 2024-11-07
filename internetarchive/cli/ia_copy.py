"""
ia_copy.py

'ia' subcommand for copying files on archive.org
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
import sys
from typing import Optional
from urllib.parse import quote

from requests import Response

import internetarchive as ia
from internetarchive.cli.cli_utils import prepare_args_dict
from internetarchive.utils import get_s3_xml_text, merge_dictionaries


def setup(subparsers):
    """
    Setup args for copy command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("copy",
                                   aliases=["cp"],
                                   help="Copy files from archive.org items")
    # Positional arguments
    parser.add_argument("source",
                        metavar="SOURCE",
                        help="Source file formatted as: identifier/file")
    parser.add_argument("destination",
                        metavar="DESTINATION",
                        help="Destination file formatted as: identifier/file")

    # Options
    parser.add_argument("-m", "--metadata",
                        metavar="KEY:VALUE",
                        action="append",
                        help=("Metadata to add to your new item, if you are moving the "
                              "file to a new item"))
    parser.add_argument("--replace-metadata",
                        action="store_true",
                        help=("Only use metadata specified as argument, do not copy any "
                              "from the source item"))
    parser.add_argument("-H", "--header",
                        metavar="KEY:VALUE",
                        action="append",
                        help="S3 HTTP headers to send with your request")
    parser.add_argument("--ignore-file-metadata",
                        action="store_true",
                        help="Do not copy file metadata")
    parser.add_argument("-n", "--no-derive",
                        action="store_true",
                        help="Do not derive uploaded files")
    parser.add_argument("--no-backup",
                        action="store_true",
                        help=("Turn off archive.org backups, "
                              "clobbered files will not be saved to "
                              "'history/files/$key.~N~'"))

    parser.set_defaults(func=lambda args: main(args, "copy", parser))


def assert_src_file_exists(src_location: str) -> bool:
    """
    Assert that the source file exists on archive.org.
    """
    assert SRC_ITEM.exists  # type: ignore
    global SRC_FILE
    src_filename = src_location.split("/", 1)[-1]
    SRC_FILE = SRC_ITEM.get_file(src_filename)  # type: ignore
    assert SRC_FILE.exists  # type: ignore
    return True


def main(args: argparse.Namespace,
         cmd: str,
         parser: argparse.ArgumentParser) -> tuple[Response, ia.files.File | None]:
    """
    Main entry point for 'ia copy'.
    """
    SRC_FILE = None

    args.header = prepare_args_dict(args.header, parser=parser, arg_type="header")
    args.metadata = prepare_args_dict(args.metadata, parser=parser, arg_type="metadata")

    if args.source == args.destination:
        parser.error("error: The source and destination files cannot be the same!")

    global SRC_ITEM
    SRC_ITEM = args.session.get_item(args.source.split("/")[0])  # type: ignore

    try:
        assert_src_file_exists(args.source)
    except AssertionError:
        parser.error(f"error: https://{args.session.host}/download/{args.source} "
                      "does not exist. Please check the "
                      "identifier and filepath and retry.")

    args.header["x-amz-copy-source"] = f"/{quote(args.source)}"
    # Copy the old metadata verbatim if no additional metadata is supplied,
    # else combine the old and the new metadata in a sensible manner.
    if args.metadata or args.replace_metadata:
        args.header["x-amz-metadata-directive"] = "REPLACE"
    else:
        args.header["x-amz-metadata-directive"] = "COPY"

    # New metadata takes precedence over old metadata.
    if not args.replace_metadata:
        args.metadata = merge_dictionaries(SRC_ITEM.metadata,  # type: ignore
                                                args.metadata)

    # File metadata is copied by default but can be dropped.
    file_metadata = None if args.ignore_file_metadata else SRC_FILE.metadata  # type: ignore

    # Add keep-old-version by default.
    if not args.header.get("x-archive-keep-old-version") and not args.no_backup:
        args.header["x-archive-keep-old-version"] = "1"

    url = f"{args.session.protocol}//s3.us.archive.org/{quote(args.destination)}"
    queue_derive = not args.no_derive
    req = ia.iarequest.S3Request(url=url,
                                 method="PUT",
                                 metadata=args.metadata,
                                 file_metadata=file_metadata,
                                 headers=args.header,
                                 queue_derive=queue_derive,
                                 access_key=args.session.access_key,
                                 secret_key=args.session.secret_key)
    p = req.prepare()
    r = args.session.send(p)
    if r.status_code != 200:
        try:
            msg = get_s3_xml_text(r.text)
        except Exception as e:
            msg = r.text
        print(f"error: failed to {cmd} '{args.source}' to '{args.destination}' - {msg}",
              file=sys.stderr)
        sys.exit(1)
    elif cmd == "copy":
        print(f"success: copied '{args.source}' to '{args.destination}'.",
              file=sys.stderr)
    return (r, SRC_FILE)
