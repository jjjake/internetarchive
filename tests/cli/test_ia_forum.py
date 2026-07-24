import json
from pathlib import Path

import pytest
import responses

from internetarchive.cli import ia_forum
from tests.conftest import ia_call

DATA = Path(__file__).parent.parent / "data" / "forums"
OFFSHOOT_URL = "https://archive.org/services/offshoot/forum-posts.php"
POST_NEW_URL = "https://archive.org/iathreads/post-new.php"


@pytest.fixture
def cookie_config(tmp_path):
    """A config file with login cookies (fake), for write-verb tests."""
    ini = tmp_path / "ia_cookies.ini"
    ini.write_text("[cookies]\nlogged-in-user = tester\nlogged-in-sig = test-sig\n")
    return str(ini)


def test_insert_default_verb_bare_identifier():
    argv = ia_forum.insert_default_verb(["forum", "GratefulDead"])
    assert argv == ["forum", "list", "GratefulDead"]


def test_insert_default_verb_explicit_verb_unchanged():
    argv = ["forum", "read", "2445301"]
    assert ia_forum.insert_default_verb(argv) == argv


def test_insert_default_verb_flag_unchanged():
    assert ia_forum.insert_default_verb(["forum", "-h"]) == ["forum", "-h"]


def test_insert_default_verb_bare_forum_unchanged():
    assert ia_forum.insert_default_verb(["forum"]) == ["forum"]


def test_insert_default_verb_escape_hatch():
    # a collection literally named "list": ia forum list list
    argv = ["forum", "list", "list"]
    assert ia_forum.insert_default_verb(argv) == argv


def test_insert_default_verb_no_forum_token():
    argv = ["search", "forum stuff"]
    assert ia_forum.insert_default_verb(argv) == argv


def test_insert_default_verb_global_flags_before_forum():
    argv = ia_forum.insert_default_verb(["--log", "forum", "GratefulDead"])
    assert argv == ["--log", "forum", "list", "GratefulDead"]


def test_ia_forum_list(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            OFFSHOOT_URL,
            body=(DATA / "offshoot_listing.json").read_text(),
            content_type="application/json",
        )
        ia_call(["ia", "forum", "list", "GratefulDead"])
    out, _err = capsys.readouterr()
    assert "2445301" in out
    assert "First and Last GD Song You Saw" in out
    assert "wlg3" in out


def test_ia_forum_bare_identifier_lists(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            OFFSHOOT_URL,
            body=(DATA / "offshoot_listing.json").read_text(),
            content_type="application/json",
        )
        ia_call(["ia", "forum", "GratefulDead"])
    out, _err = capsys.readouterr()
    assert "2445301" in out


def test_ia_forum_list_json(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            OFFSHOOT_URL,
            body=(DATA / "offshoot_listing.json").read_text(),
            content_type="application/json",
        )
        ia_call(["ia", "forum", "list", "GratefulDead", "--json"])
    out, _err = capsys.readouterr()
    lines = [json.loads(line) for line in out.splitlines() if line]
    assert [t["id"] for t in lines] == ["2445301", "2445295"]
    assert lines[0]["date"] == "2026-07-23T07:26:00"


def test_ia_forum_list_not_found(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            OFFSHOOT_URL,
            json={"success": True, "value": {"exists": False, "html": None}},
        )
        ia_call(["ia", "forum", "list", "nosuchforum"], expected_exit_code=1)
    _out, err = capsys.readouterr()
    assert "does not exist" in err


def test_ia_forum_read(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://archive.org/post/2445301",
            body=(DATA / "thread.html").read_text(),
        )
        ia_call(["ia", "forum", "read", "2445301"])
    out, _err = capsys.readouterr()
    assert "[2445301] wlg3" in out
    assert "Days Between" in out
    # the reply is indented under the root
    assert "  [2445303] c-freedom" in out


def test_ia_forum_read_json(capsys):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://archive.org/post/2445301",
            body=(DATA / "thread.html").read_text(),
        )
        ia_call(["ia", "forum", "read", "2445301", "--json"])
    out, _err = capsys.readouterr()
    thread = json.loads(out)
    assert thread["id"] == "2445301"
    assert thread["forum_id"] == "GratefulDead"
    assert len(thread["posts"]) == 2


def test_ia_forum_post_dry_run(capsys, cookie_config):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            POST_NEW_URL,
            body=(DATA / "compose_form.html").read_text(),
        )
        ia_call(
            [
                "ia",
                "--config-file",
                cookie_config,
                "forum",
                "post",
                "GratefulDead",
                "--subject",
                "A subject",
                "--body",
                "A body",
                "--dry-run",
            ]
        )
    out, _err = capsys.readouterr()
    assert "dry run" in out.lower()
    assert "postsubject" in out
    assert "A subject" in out
    assert "Submit Post" in out


def test_ia_forum_reply_dry_run_resolves_forum(capsys, cookie_config):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            "https://archive.org/post/2445301",
            body=(DATA / "thread.html").read_text(),
        )
        rsps.add(
            responses.GET,
            POST_NEW_URL,
            body=(DATA / "compose_form.html").read_text(),
        )
        ia_call(
            [
                "ia",
                "--config-file",
                cookie_config,
                "forum",
                "reply",
                "2445301",
                "--body",
                "A reply",
                "--dry-run",
            ]
        )
    out, _err = capsys.readouterr()
    # forum and subject resolved from the thread page, parent defaults to root
    assert "GratefulDead" in out
    assert "Re: First and Last GD Song You Saw" in out
    assert "parentid" in out


def test_ia_forum_post_rejected(capsys, cookie_config):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            POST_NEW_URL,
            body=(DATA / "compose_form.html").read_text(),
        )
        rsps.add(
            responses.POST,
            POST_NEW_URL,
            body=(DATA / "post_failure.html").read_text(),
        )
        ia_call(
            [
                "ia",
                "--config-file",
                cookie_config,
                "forum",
                "post",
                "GratefulDead",
                "--subject",
                "s",
                "--body",
                "b",
            ],
            expected_exit_code=1,
        )
    _out, err = capsys.readouterr()
    assert "usual causes" in err


def test_ia_forum_post_success_shows_recent_threads(capsys, cookie_config):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.GET,
            POST_NEW_URL,
            body=(DATA / "compose_form.html").read_text(),
        )
        rsps.add(
            responses.POST,
            POST_NEW_URL,
            body=(DATA / "post_success.html").read_text(),
        )
        rsps.add(
            responses.GET,
            OFFSHOOT_URL,
            body=(DATA / "offshoot_listing.json").read_text(),
            content_type="application/json",
        )
        ia_call(
            [
                "ia",
                "--config-file",
                cookie_config,
                "forum",
                "post",
                "GratefulDead",
                "--subject",
                "s",
                "--body",
                "b",
            ]
        )
    out, _err = capsys.readouterr()
    assert "success" in out.lower()
    assert "First and Last GD Song You Saw" in out


def test_ia_forum_create_dry_run(capsys, cookie_config):
    ia_call(
        [
            "ia",
            "--config-file",
            cookie_config,
            "forum",
            "create",
            "mycoll",
            "--name",
            "My Forum",
            "--dry-run",
        ]
    )
    out, _err = capsys.readouterr()
    assert "forumid" in out
    assert "mycoll" in out
    assert "Create Forum" in out
