#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2026 Internet Archive
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
internetarchive.style
~~~~~~~~~~~~~~~~~~~~~

Terminal styling helpers for the ``ia`` CLI.

Provides progress-bar configuration and ANSI formatting that
degrades gracefully when output is not a TTY or when the
``NO_COLOR`` environment variable is set.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import annotations

import os
import sys
from typing import IO, Any


def _color_enabled(file: IO[str] = sys.stderr) -> bool:
    """Return ``True`` when ANSI escape sequences are safe to emit.

    Colour is disabled when:

    * The ``NO_COLOR`` environment variable is set (any value).
    * *file* is not connected to a TTY.

    :param file: The output stream to check (default ``sys.stderr``).
    :returns: Whether colour output is enabled.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    return hasattr(file, "isatty") and file.isatty()


def dim(text: str, file: IO[str] = sys.stderr) -> str:
    """Wrap *text* in ANSI dim (faint) codes when colour is enabled.

    :param text: The string to dim.
    :param file: The output stream used to decide colour support.
    :returns: The original or dim-wrapped text.
    """
    if _color_enabled(file):
        return f"\033[2m{text}\033[0m"
    return text


def download_bar_kwargs(
    desc: str,
    total: int | None,
    file: IO[str] = sys.stderr,
) -> dict[str, Any]:
    """Return a ``dict`` of tqdm kwargs for a download progress bar.

    :param desc: The bar description (e.g. ``' downloading file.zip'``).
    :param total: Total bytes, or ``None`` if unknown.
    :param file: The output stream for colour detection.
    :returns: A ``dict`` suitable for unpacking into ``tqdm(**...)``.
    """
    kwargs: dict[str, Any] = {
        "desc": desc,
        "total": total,
        "ascii": " -",
        "bar_format": (
            "{desc} {percentage:3.0f}% {bar} "
            "{n_fmt}/{total_fmt} {rate_fmt}"
        ),
        "unit": "iB",
        "unit_scale": True,
        "unit_divisor": 1024,
        "dynamic_ncols": True,
        "leave": False,
    }
    if _color_enabled(file):
        kwargs["colour"] = "green"
    return kwargs


def _truncate(text: str, width: int) -> str:
    """Truncate *text* to *width* characters with an ellipsis.

    :param text: The string to truncate.
    :param width: Maximum visible width.
    :returns: The original or truncated text.
    """
    if len(text) <= width:
        return text
    return text[: width - 1] + "\u2026"


_DESC_WIDTH = 50


def format_download_desc(
    filename: str,
    file: IO[str] = sys.stderr,
) -> str:
    """Format a download bar description with a dimmed filename.

    :param filename: The name of the file being downloaded.
    :param file: The output stream for colour detection.
    :returns: A description string like ``'  myfile.zip'``.
    """
    desc = _truncate(f"  {filename}", _DESC_WIDTH)
    return dim(desc, file)


def print_item_header(
    identifier: str | None,
    item_index: int | str | None = None,
    file: IO[str] = sys.stderr,
) -> None:
    """Print the item header line to *file*.

    :param identifier: The Archive.org item identifier.
    :param item_index: Optional index (e.g. ``'1/3'`` or ``1``).
    :param file: Destination stream.
    """
    if item_index:
        print(f"{identifier} ({item_index}):", file=file)
    else:
        print(f"{identifier}:", file=file)


def print_status(
    msg: str,
    file: IO[str] = sys.stderr,
) -> None:
    """Print a dimmed status message with a leading space.

    :param msg: The status message to print.
    :param file: Destination stream.
    """
    print(f" {dim(msg, file)}", file=file)


def print_completed_bar(
    filename: str,
    total_fmt: str,
    file: IO[str] = sys.stderr,
) -> None:
    """Print a dimmed completion summary after a progress bar clears.

    :param filename: The name of the downloaded file.
    :param total_fmt: Human-readable total size string.
    :param file: Destination stream.
    """
    line = f"  {filename} 100% {total_fmt} done"
    print(dim(line, file), file=file)
