import argparse

from internetarchive.cli.cli_utils import (
    MetadataAction,
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
