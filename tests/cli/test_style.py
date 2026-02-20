import io
import os

import pytest

from internetarchive.style import (
    _color_enabled,
    dim,
    download_bar_kwargs,
    format_download_desc,
    print_completed_bar,
    print_item_header,
    print_status,
)


class FakeTTY(io.StringIO):
    """A StringIO that reports ``isatty() == True``."""

    def isatty(self):
        return True


class TestColorEnabled:
    def test_non_tty_returns_false(self):
        buf = io.StringIO()
        assert _color_enabled(buf) is False

    def test_tty_returns_true(self):
        buf = FakeTTY()
        assert _color_enabled(buf) is True

    def test_no_color_env_disables(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        buf = FakeTTY()
        assert _color_enabled(buf) is False

    def test_no_color_empty_string_disables(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "")
        buf = FakeTTY()
        assert _color_enabled(buf) is False

    def test_no_color_unset_allows(self, monkeypatch):
        monkeypatch.delenv("NO_COLOR", raising=False)
        buf = FakeTTY()
        assert _color_enabled(buf) is True


class TestDim:
    def test_dim_with_color(self):
        buf = FakeTTY()
        result = dim("hello", buf)
        assert result == "\033[2mhello\033[0m"

    def test_dim_without_color(self):
        buf = io.StringIO()
        result = dim("hello", buf)
        assert result == "hello"

    def test_dim_no_color_env(self, monkeypatch):
        monkeypatch.setenv("NO_COLOR", "1")
        buf = FakeTTY()
        result = dim("hello", buf)
        assert result == "hello"


class TestDownloadBarKwargs:
    def test_basic_keys(self):
        buf = io.StringIO()
        kwargs = download_bar_kwargs("desc", 1024, buf)
        assert kwargs["desc"] == "desc"
        assert kwargs["total"] == 1024
        assert kwargs["ascii"] == " -"
        assert kwargs["unit"] == "iB"
        assert kwargs["unit_scale"] is True
        assert kwargs["unit_divisor"] == 1024
        assert kwargs["dynamic_ncols"] is True
        assert kwargs["leave"] is False
        assert "colour" not in kwargs

    def test_colour_on_tty(self):
        buf = FakeTTY()
        kwargs = download_bar_kwargs("desc", 1024, buf)
        assert kwargs["colour"] == "green"

    def test_no_colour_on_non_tty(self):
        buf = io.StringIO()
        kwargs = download_bar_kwargs("desc", 1024, buf)
        assert "colour" not in kwargs

    def test_total_none(self):
        buf = io.StringIO()
        kwargs = download_bar_kwargs("desc", None, buf)
        assert kwargs["total"] is None

    def test_bar_format(self):
        buf = io.StringIO()
        kwargs = download_bar_kwargs("desc", 100, buf)
        assert "{percentage:3.0f}%" in kwargs["bar_format"]
        assert "{bar}" in kwargs["bar_format"]
        assert "{rate_fmt}" in kwargs["bar_format"]


class TestFormatDownloadDesc:
    def test_non_tty_plain(self):
        buf = io.StringIO()
        result = format_download_desc("myfile.zip", buf)
        assert result == " downloading myfile.zip"

    def test_tty_dims_filename(self):
        buf = FakeTTY()
        result = format_download_desc("myfile.zip", buf)
        assert "downloading" in result
        assert "\033[2mmyfile.zip\033[0m" in result


class TestPrintItemHeader:
    def test_with_index(self):
        buf = io.StringIO()
        print_item_header("my-item", "1/3", file=buf)
        assert buf.getvalue() == "my-item (1/3):\n"

    def test_without_index(self):
        buf = io.StringIO()
        print_item_header("my-item", file=buf)
        assert buf.getvalue() == "my-item:\n"

    def test_none_index(self):
        buf = io.StringIO()
        print_item_header("my-item", None, file=buf)
        assert buf.getvalue() == "my-item:\n"


class TestPrintStatus:
    def test_leading_space(self):
        buf = io.StringIO()
        print_status("skipping item, already exists", file=buf)
        output = buf.getvalue()
        assert output.startswith(" ")
        assert "skipping item, already exists" in output

    def test_no_ansi_on_non_tty(self):
        buf = io.StringIO()
        print_status("some message", file=buf)
        output = buf.getvalue()
        assert "\033[" not in output

    def test_ansi_on_tty(self):
        buf = FakeTTY()
        print_status("some message", file=buf)
        output = buf.getvalue()
        assert "\033[2m" in output


class TestPrintCompletedBar:
    def test_non_tty_plain(self):
        buf = io.StringIO()
        print_completed_bar("file.zip", "4.2KiB", file=buf)
        output = buf.getvalue()
        assert "downloading file.zip" in output
        assert "100%" in output
        assert "4.2KiB" in output
        assert "done" in output
        assert "\033[" not in output

    def test_tty_dimmed(self):
        buf = FakeTTY()
        print_completed_bar("file.zip", "4.2KiB", file=buf)
        output = buf.getvalue()
        assert "\033[2m" in output
        assert "file.zip" in output
