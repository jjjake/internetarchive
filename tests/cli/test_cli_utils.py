import argparse

import pytest

from internetarchive.cli.cli_utils import (
    MetadataAction,
    PostDataAction,
    QueryStringAction,
    get_args_dict,
)


def test_get_args_dict():
    test_input = [
        'collection:test_collection',
        'description: Attention: multiple colons',
        'unicode_test:தமிழ்',
        'subject:subject1, subject1',
        'subject:subject2',
        'subject:subject3; subject3',
    ]
    test_output = {
        'collection': 'test_collection',
        'description': ' Attention: multiple colons',
        'unicode_test': 'தமிழ்',
        'subject': ['subject1, subject1', 'subject2', 'subject3; subject3'],
    }
    args_dict = get_args_dict(test_input)
    for key, value in args_dict.items():
        assert test_output[key] == value


def test_get_args_dict_query_string():
    test_input = ['a=b,foo&c=d&e=f', 'foo:bar ']
    test_output = {
        'a': 'b,foo',
        'c': 'd',
        'e': 'f',
        'foo': 'bar ',
    }
    args_dict = get_args_dict(test_input, query_string=True)
    for key, value in args_dict.items():
        assert test_output[key] == value


class TestParserReuseIsolation:
    """Verify that parsing twice with the same parser doesn't leak state."""

    def test_metadata_action_parser_reuse(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs="+", action=MetadataAction,
                            default=None)
        args1 = parser.parse_args(["--metadata", "key1:val1"])
        args2 = parser.parse_args(["--metadata", "key2:val2"])
        assert args1.metadata == {"key1": "val1"}
        assert args2.metadata == {"key2": "val2"}

    def test_query_string_action_parser_reuse(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs="+", action=QueryStringAction,
                            default=None)
        args1 = parser.parse_args(["--param", "a=1"])
        args2 = parser.parse_args(["--param", "b=2"])
        assert args1.param == {"a": "1"}
        assert args2.param == {"b": "2"}

    def test_post_data_action_parser_reuse(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs=1, action=PostDataAction,
                            default=None)
        args1 = parser.parse_args(["--data", '{"a": 1}'])
        args2 = parser.parse_args(["--data", '{"b": 2}'])
        assert args1.data == {"a": 1}
        assert args2.data == {"b": 2}


class TestQueryStringAction:
    """Tests for QueryStringAction edge cases."""

    def test_equals_in_value(self):
        """Values containing '=' should be preserved."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs="+", action=QueryStringAction,
                            default=None)
        args = parser.parse_args(["--param", "key=a=b"])
        assert args.param == {"key": "a=b"}

    def test_invalid_input_rejected(self):
        """Input without key=value format should error."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs="+", action=QueryStringAction,
                            default=None)
        with pytest.raises(SystemExit):
            parser.parse_args(["--param", "noequalssign"])

    def test_repeated_key_accumulates(self):
        """Repeated same key across multiple --param flags."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--param", nargs=1, action=QueryStringAction,
                            default=None)
        args = parser.parse_args(
            ["--param", "a=1", "--param", "a=2"]
        )
        assert args.param == {"a": ["1", "2"]}


class TestMetadataAction:
    """Tests for MetadataAction edge cases."""

    def test_empty_value(self):
        """Empty values (key:) should be accepted."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs="+", action=MetadataAction,
                            default=None)
        args = parser.parse_args(["--metadata", "key:"])
        assert args.metadata == {"key": ""}

    def test_equals_syntax(self):
        """MetadataAction should accept '=' as separator too."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs="+", action=MetadataAction,
                            default=None)
        args = parser.parse_args(["--metadata", "key=value"])
        assert args.metadata == {"key": "value"}

    def test_invalid_input_rejected(self):
        """Input without key:value or key=value format should error."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--metadata", nargs="+", action=MetadataAction,
                            default=None)
        with pytest.raises(SystemExit):
            parser.parse_args(["--metadata", "nocolonorequals"])


class TestPostDataAction:
    """Tests for PostDataAction edge cases."""

    def test_json_with_colons_in_value(self):
        """JSON values containing colons should parse correctly."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs="+", action=PostDataAction,
                            default=None)
        args = parser.parse_args(["--data", '{"url":"http://example.com"}'])
        assert args.data == {"url": "http://example.com"}

    def test_key_value_input_accepted(self):
        """PostDataAction accepts key:value format as fallback."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs="+", action=PostDataAction,
                            default=None)
        args = parser.parse_args(["--data", "key:value"])
        assert args.data == {"key": "value"}

    def test_invalid_input_rejected(self):
        """Input without JSON, colon, or equals should error."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--data", nargs="+", action=PostDataAction,
                            default=None)
        with pytest.raises(SystemExit):
            parser.parse_args(["--data", "nocolonorequals"])


class TestMetadataSubcommandParsing:
    """Tests for ia metadata argument parsing."""

    def _make_parser(self):
        """Create a parser mimicking ia metadata's setup."""
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "-m", "--modify", nargs=1,
            action=MetadataAction, default=None,
        )
        group.add_argument(
            "-r", "--remove", nargs=1,
            action=MetadataAction, default=None,
        )
        group.add_argument(
            "-a", "--append", nargs=1,
            action=MetadataAction, default=None,
        )
        group.add_argument(
            "-A", "--append-list", nargs=1,
            action=MetadataAction, default=None,
        )
        group.add_argument(
            "-i", "--insert", nargs=1,
            action=MetadataAction, default=None,
        )
        parser.add_argument(
            "-E", "--expect", nargs=1,
            action=MetadataAction, default=None,
        )
        parser.add_argument(
            "-H", "--header", nargs=1,
            action=QueryStringAction, default=None,
        )
        return parser

    def test_modify_with_header(self):
        parser = self._make_parser()
        args = parser.parse_args([
            "--modify", "title:New Title",
            "--header", "x-custom:val",
        ])
        assert args.modify == {"title": "New Title"}
        assert args.header == {"x-custom": "val"}

    def test_mutually_exclusive_flags(self):
        parser = self._make_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "--modify", "a:b", "--remove", "c:d",
            ])
