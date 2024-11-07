"""
ia_upload.py

'ia' subcommand for uploading files to archive.org.
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
import csv
import os
import sys
import webbrowser
from copy import deepcopy
from locale import getpreferredencoding
from tempfile import TemporaryFile
from typing import Union

from requests.exceptions import HTTPError

from internetarchive.cli.cli_utils import (
    get_args_dict,
    prepare_args_dict,
    validate_identifier,
)
from internetarchive.utils import (
    InvalidIdentifierException,
    JSONDecodeError,
    is_valid_metadata_key,
    json,
)


def setup(subparsers):
    """
    Setup args for copy command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("upload",
                                   aliases=["up"],
                                   help="Upload files to archive.org")

    # Positional arguments
    parser.add_argument("identifier",
                        type=validate_identifier,
                        nargs="?",
                        default=None,
                        help="Identifier for the upload")
    parser.add_argument("file",
                        nargs="*",
                        type=validate_file,
                        help="File(s) to upload")

    # Options
    parser.add_argument("-q", "--quiet",
                        action="store_true",
                        help="Turn off ia's output")
    parser.add_argument("-d", "--debug",
                        action="store_true",
                        help=("Print S3 request parameters to stdout and exit without "
                              "sending request"))
    parser.add_argument("-r", "--remote-name",
                        help=("When uploading data from stdin, "
                             "this option sets the remote filename"))
    parser.add_argument("-m", "--metadata",
                        metavar="KEY:VALUE",
                        action="append",
                        help="Metadata to add to your item")
    parser.add_argument("--spreadsheet",
                        type=argparse.FileType("r", encoding="utf-8-sig"),
                        help="Bulk uploading")
    parser.add_argument("--file-metadata",
                        type=argparse.FileType("r"),
                        help="Upload files with file-level metadata via a file_md.jsonl file")
    parser.add_argument("-H", "--header",
                        action="append",
                        help="S3 HTTP headers to send with your request")
    parser.add_argument("-c", "--checksum",
                        action="store_true",
                        help="Skip based on checksum")
    parser.add_argument("-v", "--verify",
                        action="store_true",
                        help="Verify that data was not corrupted traversing the network")
    parser.add_argument("-n", "--no-derive",
                        action="store_true",
                        help="Do not derive uploaded files")
    parser.add_argument("--size-hint",
                        help="Specify a size-hint for your item")
    parser.add_argument("--delete",
                        action="store_true",
                        help="Delete files after verifying checksums")
    parser.add_argument("-R", "--retries",
                        type=int,
                        help="Number of times to retry request if S3 returns a 503 SlowDown error")
    parser.add_argument("-s", "--sleep",
                        type=int,
                        help="The amount of time to sleep between retries")
    parser.add_argument("--no-collection-check",
                        action="store_true",
                        help="Skip collection exists check")
    parser.add_argument("-o", "--open-after-upload",
                        action="store_true",
                        help="Open the details page for an item after upload")
    parser.add_argument("--no-backup",
                        action="store_true",
                        help="Turn off archive.org backups")
    parser.add_argument("--keep-directories",
                        action="store_true",
                        help="Keep directories in the supplied file paths for the remote filename")
    parser.add_argument("--no-scanner",
                        action="store_true",
                        help="Do not set the scanner field in meta.xml")
    parser.add_argument("--status-check",
                        action="store_true",
                        help="Check if S3 is accepting requests to the given item")

    parser.set_defaults(func=lambda args: main(args, parser))


def _upload_files(item, files, upload_kwargs, prev_identifier=None):
    """
    Helper function for calling :meth:`Item.upload`
    """
    # Check if the list has any element.
    if not files:
        raise FileNotFoundError("No valid file was found. Check your paths.")

    responses = []
    if (upload_kwargs["verbose"]) and (prev_identifier != item.identifier):
        print(f"{item.identifier}:", file=sys.stderr)

    try:
        response = item.upload(files, **upload_kwargs)
        responses += response
    except HTTPError as exc:
        responses += [exc.response]
    except InvalidIdentifierException as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        # Debug mode.
        if upload_kwargs["debug"]:
            for i, r in enumerate(responses):
                if i != 0:
                    print("---", file=sys.stderr)
                headers = "\n".join(
                    [f" {k}:{v}" for (k, v) in r.headers.items()]
                )
                print(f"Endpoint:\n {r.url}\n", file=sys.stderr)
                print(f"HTTP Headers:\n{headers}", file=sys.stderr)

    return responses


def uploading_from_stdin(args):
    """
    Check if the user is uploading from stdin.
    """
    if not args.file:
        return False
    elif len(args.file) == 1 and args.file[0] == "-":
        return True
    return False


def check_if_file_arg_required(args, parser):
    required_if_no_file = [args.spreadsheet, args.file_metadata, args.status_check]
    if not args.file and not any(required_if_no_file):
        parser.error("You must specify a file to upload.")


def validate_file(arg):
    if os.path.exists(arg) or arg == "-":
        return arg
    else:
        raise argparse.ArgumentTypeError(f"'{arg}' is not a valid file or directory")


def main(args, parser): # noqa: PLR0912,C901
    # TODO: Refactor to deal with PLR0912 and C901
    # add type hints
    """
    Main entry point for 'ia upload'.
    """

    check_if_file_arg_required(args, parser)

    if uploading_from_stdin(args) and not args.remote_name:
        parser.error("When uploading from stdin, "
                     "you must specify a remote filename with --remote-name")

    # Prepare args key:val dicts
    args.metadata = prepare_args_dict(args.metadata, parser, arg_type="metadata")
    args.header = prepare_args_dict(args.header, parser, arg_type="header")

    if args.status_check:  # TODO: support for checking if a specific bucket is overloaded
        if args.session.s3_is_overloaded():
            print(f"warning: {args.identifier} is over limit, and not accepting requests. "
                  "Expect 503 SlowDown errors.",
                  file=sys.stderr)
            sys.exit(1)
        else:
            print(f"success: {args.identifier} is accepting requests.", file=sys.stderr)
            sys.exit(0)
    elif args.identifier:
        item = args.session.get_item(args.identifier)

    # Prepare upload headers and kwargs
    if args.no_derive:
        queue_derive = False
    else:
        queue_derive = True
    if args.quiet:
        verbose = False
    else:
        verbose = True
    if args.no_scanner:
        set_scanner = False
    else:
        set_scanner = True
    if args.size_hint:
        args.header["x-archive-size-hint"] = args.size_hint
    if not args.header.get("x-archive-keep-old-version") \
            and not args.no_backup:
        args.header["x-archive-keep-old-version"] = "1"

    if args.file_metadata:
        try:
            with open(args.file_metadata) as fh:
                args.file_metadata = json.load(fh)
        except JSONDecodeError:
            args.file = []
            with open(args.file_metadata) as fh:
                for line in fh:
                    j = json.loads(line.strip())
                    args.file.append(j)

    upload_kwargs = {
        "metadata": args.metadata,
        "headers": args.header,
        "debug": args.debug,
        "queue_derive": queue_derive,
        "set_scanner": set_scanner,
        "verbose": verbose,
        "verify": args.verify,
        "checksum": args.checksum,
        "retries": args.retries,
        "retries_sleep": args.sleep,
        "delete": args.delete,
        "validate_identifier": True,
    }

    # Upload files
    errors = False
    if not args.spreadsheet:
        if uploading_from_stdin(args):
            local_file = TemporaryFile()
            # sys.stdin normally has the buffer attribute which returns bytes.
            # However, this might not always be the case, e.g. on mocking for test purposes.
            # Fall back to reading as str and encoding back to bytes.
            # Note that the encoding attribute might also be None. In that case, fall back to
            # locale.getpreferredencoding, the default of io.TextIOWrapper and open().
            if hasattr(sys.stdin, "buffer"):
                def read():
                    return sys.stdin.buffer.read(1048576)
            else:
                encoding = sys.stdin.encoding or getpreferredencoding(False)

                def read():
                    return sys.stdin.read(1048576).encode(encoding)
            while True:
                data = read()
                if not data:
                    break
                local_file.write(data)
            local_file.seek(0)
        else:
            local_file = args.file
            # Properly expand a period to the contents of the current working directory.
            if isinstance(local_file, str) and "." in local_file:
                local_file = [p for p in local_file if p != "."]
                local_file = os.listdir(".") + local_file

        if isinstance(local_file, (list, tuple, set)) and args.remote_name:
            local_file = local_file[0]
        if args.remote_name:
            files = {args.remote_name: local_file}
        elif args.keep_directories:
            files = {f: f for f in local_file}
        else:
            files = local_file

        for _r in _upload_files(item, files, upload_kwargs):
            if args.debug:
                break
            if (not _r.status_code) or (not _r.ok):
                errors = True
            else:
                if args.open_after_upload:
                    url = f"{args.session.protocol}//{args.session.host}/details/{item.identifier}"
                    webbrowser.open_new_tab(url)

    # Bulk upload using spreadsheet.
    else:
        # Use the same session for each upload request.
        with args.spreadsheet as csvfp:
            spreadsheet = csv.DictReader(csvfp)
            prev_identifier = None
            for row in spreadsheet:
                for metadata_key in row:
                    if not is_valid_metadata_key(metadata_key):
                        print(f"error: '{metadata_key}' is not a valid metadata key.",
                              file=sys.stderr)
                        sys.exit(1)
                upload_kwargs_copy = deepcopy(upload_kwargs)
                if row.get("REMOTE_NAME"):
                    local_file = {row["REMOTE_NAME"]: row["file"]}
                    del row["REMOTE_NAME"]
                elif args.keep_directories:
                    local_file = {row["file"]: row["file"]}
                else:
                    local_file = row["file"]
                identifier = row.get("item", row.get("identifier"))
                if not identifier:
                    if not prev_identifier:
                        print("error: no identifier column on spreadsheet.",
                              file=sys.stderr)
                        sys.exit(1)
                    identifier = prev_identifier
                del row["file"]
                if "identifier" in row:
                    del row["identifier"]
                if "item" in row:
                    del row["item"]
                item = args.session.get_item(identifier)
                # TODO: Clean up how indexed metadata items are coerced
                # into metadata.
                md_args = [f"{k.lower()}:{v}" for (k, v) in row.items() if v]
                metadata = get_args_dict(md_args)
                upload_kwargs_copy["metadata"].update(metadata)
                r = _upload_files(item, local_file, upload_kwargs_copy, prev_identifier)
                for _r in r:
                    if args.debug:
                        break
                    if (not _r.status_code) or (not _r.ok):
                        errors = True
                    else:
                        if args.open_after_upload:
                            url = (f"{args.session.protocol}//{args.session.host}"
                                    "/details/{identifier}")
                            webbrowser.open_new_tab(url)
                prev_identifier = identifier

    if errors:
        sys.exit(1)
