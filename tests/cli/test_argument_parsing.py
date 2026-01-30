"""
Tests for CLI argument parsing behavior.

These tests verify that:
1. Options can appear before or after positional arguments
2. Repeated flags accumulate properly (nargs=1 + action="extend" or custom actions)
3. PostDataAction works with JSON, key:value, and mixed usage
4. Edge cases with optional positional arguments
"""

import argparse

import pytest

from internetarchive.cli.cli_utils import (
    FlattenListAction,
    MetadataAction,
    PostDataAction,
    QueryStringAction,
)


class TestNargsOneWithExtend:
    """Test that nargs=1 with action='extend' accumulates properly."""

    def test_single_value(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--format", nargs=1, action="extend")
        args = parser.parse_args(["--format", "JPEG"])
        assert args.format == ["JPEG"]

    def test_multiple_flags(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--format", nargs=1, action="extend")
        args = parser.parse_args(["--format", "JPEG", "--format", "PNG"])
        assert args.format == ["JPEG", "PNG"]

    def test_flag_before_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--format", nargs=1, action="extend")
        parser.add_argument("identifier", nargs="?")
        args = parser.parse_args(["--format", "JPEG", "myitem"])
        assert args.format == ["JPEG"]
        assert args.identifier == "myitem"

    def test_flag_after_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--format", nargs=1, action="extend")
        parser.add_argument("identifier", nargs="?")
        args = parser.parse_args(["myitem", "--format", "JPEG"])
        assert args.format == ["JPEG"]
        assert args.identifier == "myitem"

    def test_mixed_flag_positions(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--format", nargs=1, action="extend")
        parser.add_argument("identifier", nargs="?")
        args = parser.parse_args(["--format", "JPEG", "myitem", "--format", "PNG"])
        assert args.format == ["JPEG", "PNG"]
        assert args.identifier == "myitem"


class TestQueryStringAction:
    """Test QueryStringAction with nargs=1."""

    def test_single_value_colon(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs=1, action=QueryStringAction)
        args = parser.parse_args(["--param", "key:value"])
        assert args.param == {"key": "value"}

    def test_single_value_equals(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs=1, action=QueryStringAction)
        args = parser.parse_args(["--param", "key=value"])
        assert args.param == {"key": "value"}

    def test_multiple_flags_different_keys(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs=1, action=QueryStringAction)
        args = parser.parse_args(["--param", "a:1", "--param", "b:2"])
        assert args.param == {"a": "1", "b": "2"}

    def test_multiple_flags_same_key(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs=1, action=QueryStringAction)
        args = parser.parse_args(["--param", "key:val1", "--param", "key:val2"])
        assert args.param == {"key": ["val1", "val2"]}

    def test_flag_before_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs=1, action=QueryStringAction)
        parser.add_argument("identifier", nargs="?")
        args = parser.parse_args(["--param", "key:value", "myitem"])
        assert args.param == {"key": "value"}
        assert args.identifier == "myitem"


class TestMetadataAction:
    """Test MetadataAction with nargs=1."""

    def test_single_value(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs=1, action=MetadataAction)
        args = parser.parse_args(["--metadata", "title:My Title"])
        assert args.metadata == {"title": "My Title"}

    def test_multiple_flags_different_keys(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs=1, action=MetadataAction)
        args = parser.parse_args(["--metadata", "title:Foo", "--metadata", "creator:Bar"])
        assert args.metadata == {"title": "Foo", "creator": "Bar"}

    def test_multiple_flags_same_key(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs=1, action=MetadataAction)
        args = parser.parse_args([
            "--metadata", "subject:topic1",
            "--metadata", "subject:topic2"
        ])
        assert args.metadata == {"subject": ["topic1", "topic2"]}

    def test_value_with_colons(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs=1, action=MetadataAction)
        args = parser.parse_args(["--metadata", "description:Time: 10:30 AM"])
        assert args.metadata == {"description": "Time: 10:30 AM"}

    def test_flag_before_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs=1, action=MetadataAction)
        parser.add_argument("identifier", nargs="?")
        args = parser.parse_args(["--metadata", "title:Foo", "myitem"])
        assert args.metadata == {"title": "Foo"}
        assert args.identifier == "myitem"


class TestPostDataAction:
    """Test PostDataAction with JSON and key:value support."""

    def test_json_object(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        args = parser.parse_args(["--data", '{"priority": 10}'])
        assert args.data == {"priority": 10}

    def test_key_value_colon(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        args = parser.parse_args(["--data", "priority:10"])
        assert args.data == {"priority": "10"}

    def test_key_value_equals(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        args = parser.parse_args(["--data", "priority=10"])
        assert args.data == {"priority": "10"}

    def test_multiple_json_flags(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        args = parser.parse_args([
            "--data", '{"priority": 10}',
            "--data", '{"comment": "test"}'
        ])
        assert args.data == {"priority": 10, "comment": "test"}

    def test_multiple_key_value_flags(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        args = parser.parse_args(["--data", "a:1", "--data", "b:2"])
        assert args.data == {"a": "1", "b": "2"}

    def test_mixed_json_and_key_value(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        args = parser.parse_args([
            "--data", '{"priority": 10}',
            "--data", "comment:test"
        ])
        assert args.data == {"priority": 10, "comment": "test"}

    def test_json_overwrites_key(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        args = parser.parse_args([
            "--data", "priority:5",
            "--data", '{"priority": 10}'
        ])
        assert args.data == {"priority": 10}

    def test_flag_before_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        parser.add_argument("identifier", nargs="?")
        args = parser.parse_args(["--data", "key:value", "myitem"])
        assert args.data == {"key": "value"}
        assert args.identifier == "myitem"

    def test_invalid_format_error(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        with pytest.raises(SystemExit):
            parser.parse_args(["--data", "invalid"])

    def test_json_array_error(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction, default={})
        with pytest.raises(SystemExit):
            parser.parse_args(["--data", "[1, 2, 3]"])


class TestFlattenListAction:
    """Test FlattenListAction with nargs=1."""

    def test_single_value(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--field", nargs=1, action=FlattenListAction)
        args = parser.parse_args(["--field", "identifier"])
        assert args.field == ["identifier"]

    def test_multiple_flags(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--field", nargs=1, action=FlattenListAction)
        args = parser.parse_args(["--field", "identifier", "--field", "title"])
        assert args.field == ["identifier", "title"]

    def test_flag_before_positional(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--field", nargs=1, action=FlattenListAction)
        parser.add_argument("query", nargs="?")
        args = parser.parse_args(["--field", "title", "cats"])
        assert args.field == ["title"]
        assert args.query == "cats"


class TestDownloadArgParsing:
    """Test ia download argument parsing specifically."""

    def setup_method(self):
        """Set up a parser that mimics ia download."""
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument("identifier", nargs="?")
        self.parser.add_argument("file", nargs="*")
        self.parser.add_argument("--format", "-f", nargs=1, action="extend")
        self.parser.add_argument("--source", nargs=1, action="extend")

    def test_format_after_identifier(self):
        args = self.parser.parse_args(["myitem", "--format", "JPEG"])
        assert args.identifier == "myitem"
        assert args.format == ["JPEG"]

    def test_format_before_identifier(self):
        args = self.parser.parse_args(["--format", "JPEG", "myitem"])
        assert args.identifier == "myitem"
        assert args.format == ["JPEG"]

    def test_multiple_formats_before_identifier(self):
        args = self.parser.parse_args([
            "--format", "JPEG",
            "--format", "PNG",
            "myitem"
        ])
        assert args.identifier == "myitem"
        assert args.format == ["JPEG", "PNG"]

    def test_formats_on_both_sides(self):
        args = self.parser.parse_args([
            "--format", "JPEG",
            "myitem",
            "--format", "PNG"
        ])
        assert args.identifier == "myitem"
        assert args.format == ["JPEG", "PNG"]

    def test_with_file_argument(self):
        args = self.parser.parse_args([
            "myitem",
            "file1.txt",
            "--format", "JPEG"
        ])
        assert args.identifier == "myitem"
        assert args.file == ["file1.txt"]
        assert args.format == ["JPEG"]


class TestUploadArgParsing:
    """Test ia upload argument parsing specifically."""

    def setup_method(self):
        """Set up a parser that mimics ia upload."""
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument("identifier", nargs="?")
        self.parser.add_argument("file", nargs="*")
        self.parser.add_argument("--metadata", "-m", nargs=1, action=MetadataAction,
                                 default={})

    def test_metadata_after_identifier(self):
        args = self.parser.parse_args([
            "myitem", "file.txt",
            "--metadata", "title:My Title"
        ])
        assert args.identifier == "myitem"
        assert args.file == ["file.txt"]
        assert args.metadata == {"title": "My Title"}

    def test_metadata_before_identifier(self):
        args = self.parser.parse_args([
            "--metadata", "title:My Title",
            "myitem", "file.txt"
        ])
        assert args.identifier == "myitem"
        assert args.file == ["file.txt"]
        assert args.metadata == {"title": "My Title"}

    def test_multiple_metadata(self):
        args = self.parser.parse_args([
            "--metadata", "title:My Title",
            "--metadata", "creator:Author",
            "myitem", "file.txt"
        ])
        assert args.identifier == "myitem"
        assert args.metadata == {"title": "My Title", "creator": "Author"}
