import json
from pathlib import Path

import pytest
import responses

import internetarchive
from internetarchive import forums, get_session
from internetarchive.exceptions import (
    AuthenticationError,
    ForumError,
    ForumNotFoundError,
)

DATA = Path(__file__).parent / "data" / "forums"
OFFSHOOT_URL = "https://archive.org/services/offshoot/forum-posts.php"
TEST_CONFIG = str(Path(__file__).parent / "ia.ini")


def _session(cookies=True):
    config = {}
    if cookies:
        config["cookies"] = {
            "logged-in-user": "test%40example.com",
            "logged-in-sig": "test-sig",
        }
    return get_session(config=config, config_file=TEST_CONFIG)


def _backend(cookies=True):
    return forums._IathreadsBackend(_session(cookies=cookies))


def _listing_html():
    return json.loads((DATA / "offshoot_listing.json").read_text())["value"]["html"]


def test_parse_date():
    d = forums._parse_date("Jul 23, 2026 7:26am")
    assert d.isoformat() == "2026-07-23T07:26:00"
    d = forums._parse_date(" Dec 1, 2025 11:59pm ")
    assert d.isoformat() == "2025-12-01T23:59:00"


def test_parse_listing_groups_threads():
    threads = forums._parse_listing(_listing_html())
    assert [t.id for t in threads] == ["2445301", "2445295"]
    t = threads[0]
    assert t.subject == "First and Last GD Song You Saw"
    assert t.poster == "wlg3"
    assert t.replies == 1
    assert t.date.isoformat() == "2026-07-23T07:26:00"
    # last_post_date comes from the indented "Re:" row that follows the root
    assert t.last_post_date > t.date


def test_parse_listing_unescapes_entities():
    threads = forums._parse_listing(_listing_html())
    assert threads[1].subject == "BERTHA don’t you come a round here"


def test_parse_thread_posts():
    thread = forums._parse_thread((DATA / "thread.html").read_text())
    assert thread.id == "2445301"
    assert thread.forum_id == "GratefulDead"
    assert thread.subject == "First and Last GD Song You Saw"
    assert len(thread.posts) == 2
    root, reply = thread.posts
    assert (root.id, root.depth, root.parent_id) == ("2445301", 0, None)
    assert (reply.id, reply.depth, reply.parent_id) == ("2445303", 1, "2445301")
    assert root.thread_id == "2445301"
    assert root.poster == "wlg3"
    assert root.date.isoformat() == "2026-07-23T07:26:00"
    assert root.subject == "First and Last GD Song You Saw"
    assert "Days Between" in root.body
    assert "<br" not in root.body
    assert "<br" in root.body_html


def test_parse_thread_body_newlines_and_entities():
    thread = forums._parse_thread((DATA / "thread.html").read_text())
    root = thread.posts[0]
    # <br /><br /> becomes newlines; &amp; is unescaped
    assert "\n" in root.body
    assert "Dead & Co" in root.body


@responses.activate
def test_backend_exists():
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": True, "value": {"exists": True, "html": ""}},
    )
    assert _backend().exists("GratefulDead") is True


@responses.activate
def test_backend_exists_false():
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": True, "value": {"exists": False, "html": None}},
    )
    assert _backend().exists("nosuchforum") is False


@responses.activate
def test_backend_offshoot_envelope_error():
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": False, "error": '"forum_id" not found'},
    )
    with pytest.raises(ForumError, match="forum_id"):
        _backend().list_posts("GratefulDead")


@responses.activate
def test_backend_list_posts():
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        body=(DATA / "offshoot_listing.json").read_text(),
        content_type="application/json",
    )
    threads = _backend().list_posts("GratefulDead")
    assert [t.id for t in threads] == ["2445301", "2445295"]


@responses.activate
def test_backend_list_posts_not_found():
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": True, "value": {"exists": False, "html": None}},
    )
    with pytest.raises(ForumNotFoundError, match="ia forum create"):
        _backend().list_posts("nosuchforum")


@responses.activate
def test_backend_list_posts_format_changed():
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={
            "success": True,
            "value": {"exists": True, "html": "<div>redesigned!</div>"},
        },
    )
    with pytest.raises(ForumError, match="format may have changed"):
        _backend().list_posts("GratefulDead")


@responses.activate
def test_backend_get_thread():
    responses.add(
        responses.GET,
        "https://archive.org/post/2445301",
        body=(DATA / "thread.html").read_text(),
    )
    thread = _backend().get_thread("2445301")
    assert thread.id == "2445301"
    assert thread.forum_id == "GratefulDead"
    assert len(thread.posts) == 2


@responses.activate
def test_backend_get_thread_not_found():
    responses.add(responses.GET, "https://archive.org/post/999999999", status=404)
    with pytest.raises(ForumNotFoundError, match="999999999"):
        _backend().get_thread("999999999")


@responses.activate
def test_backend_get_thread_format_changed():
    responses.add(
        responses.GET,
        "https://archive.org/post/2445301",
        body="<html><body>redesigned!</body></html>",
    )
    with pytest.raises(ForumError, match="format may have changed"):
        _backend().get_thread("2445301")


POST_NEW_URL = "https://archive.org/iathreads/post-new.php"
FORUM_NEW_URL = "https://archive.org/iathreads/forum-new.php"


def _compose_form():
    return (DATA / "compose_form.html").read_text()


def _last_request_body():
    return responses.calls[-1].request.body


def test_require_auth_no_cookies():
    with pytest.raises(AuthenticationError, match="ia configure"):
        _backend(cookies=False)._require_auth()


def test_require_auth_with_cookies():
    _backend()._require_auth()  # should not raise


@responses.activate
def test_submit_post_fields():
    responses.add(responses.GET, POST_NEW_URL, body=_compose_form())
    responses.add(
        responses.POST, POST_NEW_URL, body=(DATA / "post_success.html").read_text()
    )
    _backend().submit_post("GratefulDead", "A subject", "A body")
    body = _last_request_body()
    if isinstance(body, bytes):
        body = body.decode()
    # multipart fields echo the scraped form values
    assert "eyJHDR.eyJub25jZSI6ImFiYzEyMyJ9.SIG" in body
    assert "2026-07-23 17:00:00" in body
    assert 'name="postsubject"' in body
    assert "A subject" in body
    assert 'name="postbody"' in body
    assert "A body" in body
    assert 'name="forum"' in body
    assert "GratefulDead" in body
    assert 'name="referer"' in body
    # the real submit button, NOT the "Add Files" attachment button
    assert "Submit Post" in body
    assert "Add Files" not in body
    # form fetch targeted the right compose URL
    assert responses.calls[0].request.url.startswith(POST_NEW_URL)
    assert "forum=GratefulDead" in responses.calls[0].request.url


@responses.activate
def test_submit_reply_fields():
    responses.add(responses.GET, POST_NEW_URL, body=_compose_form())
    responses.add(
        responses.POST, POST_NEW_URL, body=(DATA / "post_success.html").read_text()
    )
    _backend().submit_reply(
        "GratefulDead", "2445301", "2445303", "Re: A subject", "A reply"
    )
    form_url = responses.calls[0].request.url
    assert "reply=1" in form_url
    assert "parentid=2445303" in form_url
    assert "threadid=2445301" in form_url
    assert "nested=1" in form_url
    body = _last_request_body()
    if isinstance(body, bytes):
        body = body.decode()
    assert 'name="parentid"' in body
    assert "2445303" in body
    assert 'name="threadid"' in body
    assert "2445301" in body
    assert 'name="nested"' in body


@responses.activate
def test_submit_edit_fields():
    responses.add(responses.GET, POST_NEW_URL, body=_compose_form())
    responses.add(
        responses.POST, POST_NEW_URL, body=(DATA / "edit_success.html").read_text()
    )
    _backend().submit_edit(
        "GratefulDead", "2445303", "2445301", "New subject", "New body"
    )
    form_url = responses.calls[0].request.url
    assert "action=edit" in form_url
    assert "id=2445303" in form_url
    assert "threadid=2445301" in form_url
    body = _last_request_body()
    if isinstance(body, bytes):
        body = body.decode()
    assert 'name="action"' in body
    assert "edit" in body
    assert 'name="id"' in body


@responses.activate
def test_submit_post_rejected():
    responses.add(responses.GET, POST_NEW_URL, body=_compose_form())
    responses.add(
        responses.POST, POST_NEW_URL, body=(DATA / "post_failure.html").read_text()
    )
    with pytest.raises(ForumError, match="usual causes"):
        _backend().submit_post("GratefulDead", "s", "b")


@responses.activate
def test_submit_post_no_csrf_missing_forum():
    responses.add(
        responses.GET,
        POST_NEW_URL,
        body=(DATA / "compose_form_nocsrf.html").read_text(),
    )
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": True, "value": {"exists": False, "html": None}},
    )
    with pytest.raises(ForumNotFoundError, match="ia forum create"):
        _backend().submit_post("nosuchforum", "s", "b")


@responses.activate
def test_submit_post_no_csrf_stale_cookies():
    responses.add(
        responses.GET,
        POST_NEW_URL,
        body=(DATA / "compose_form_nocsrf.html").read_text(),
    )
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": True, "value": {"exists": True, "html": ""}},
    )
    with pytest.raises(AuthenticationError, match="stale"):
        _backend().submit_post("GratefulDead", "s", "b")


@responses.activate
def test_submit_post_dry_run_does_not_post():
    # only the GET is registered: a POST would error the test
    responses.add(responses.GET, POST_NEW_URL, body=_compose_form())
    fields = _backend().submit_post("GratefulDead", "A subject", "A body", dry_run=True)
    assert fields["postsubject"] == "A subject"
    assert fields["submit"] == "Submit Post"
    assert fields["csrf_token"].startswith("eyJHDR.")
    assert len(responses.calls) == 1


@responses.activate
def test_create_forum_fields_and_verify():
    responses.add(responses.POST, FORUM_NEW_URL, body="<title>ok</title>")
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": True, "value": {"exists": True, "html": ""}},
    )
    _backend().create_forum(
        "mycoll", "My Collection Forum", "/details/mycoll?tab=forum", "0", "0"
    )
    body = responses.calls[0].request.body
    assert "action=create" in body
    assert "forumid=mycoll" in body
    assert "forumname=My+Collection+Forum" in body
    assert "forumhome=%2Fdetails%2Fmycoll%3Ftab%3Dforum" in body
    assert "public_read=0" in body
    assert "public_write=0" in body
    assert "submit=Create+Forum" in body
    # creation is verified via a follow-up Offshoot existence read
    assert "forum_id=mycoll" in responses.calls[1].request.url


@responses.activate
def test_create_forum_unauthorized():
    responses.add(responses.POST, FORUM_NEW_URL, status=401)
    with pytest.raises(AuthenticationError, match="not authorized"):
        _backend().create_forum("mycoll", "Name", None, "0", "0")


@responses.activate
def test_create_forum_verify_fails():
    responses.add(responses.POST, FORUM_NEW_URL, body="<title>ok</title>")
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        json={"success": True, "value": {"exists": False, "html": None}},
    )
    with pytest.raises(ForumError, match="was not created"):
        _backend().create_forum("mycoll", "Name", None, "0", "0")


@responses.activate
def test_forum_construction_is_cheap():
    # no responses registered: any HTTP request would fail the test
    forum = _session().get_forum("GratefulDead")
    assert forum.identifier == "GratefulDead"


@responses.activate
def test_forum_threads_and_thread():
    responses.add(
        responses.GET,
        OFFSHOOT_URL,
        body=(DATA / "offshoot_listing.json").read_text(),
        content_type="application/json",
    )
    responses.add(
        responses.GET,
        "https://archive.org/post/2445301",
        body=(DATA / "thread.html").read_text(),
    )
    forum = _session().get_forum("GratefulDead")
    assert [t.id for t in forum.threads()] == ["2445301", "2445295"]
    assert forum.thread("2445301").forum_id == "GratefulDead"


@responses.activate
def test_forum_reply_defaults():
    # subject defaults to "Re: <root subject>", parent to the thread root
    responses.add(
        responses.GET,
        "https://archive.org/post/2445301",
        body=(DATA / "thread.html").read_text(),
    )
    responses.add(responses.GET, POST_NEW_URL, body=_compose_form())
    forum = _session().get_forum("GratefulDead")
    fields = forum.reply("2445301", "body text", dry_run=True)
    assert fields["postsubject"] == "Re: First and Last GD Song You Saw"
    assert fields["parentid"] == "2445301"
    assert fields["threadid"] == "2445301"


@responses.activate
def test_forum_reply_no_double_re_prefix():
    responses.add(responses.GET, POST_NEW_URL, body=_compose_form())
    forum = _session().get_forum("GratefulDead")
    fields = forum.reply("2445301", "b", subject="Re: Already prefixed", dry_run=True)
    assert fields["postsubject"] == "Re: Already prefixed"
    # explicit subject: the thread page is never fetched
    assert len(responses.calls) == 1


@responses.activate
def test_module_get_thread():
    responses.add(
        responses.GET,
        "https://archive.org/post/2445301",
        body=(DATA / "thread.html").read_text(),
    )
    thread = forums.get_thread(_session(), "2445301")
    assert thread.id == "2445301"
    assert thread.forum_id == "GratefulDead"


def test_item_get_forum_factory():
    session = _session()
    item = session.get_item(
        "GratefulDead",
        item_metadata={"metadata": {"identifier": "GratefulDead"}},
    )
    forum = item.get_forum()
    assert isinstance(forum, forums.Forum)
    assert forum.identifier == "GratefulDead"
    assert forum.session is session


def test_api_get_forum_factory():
    forum = internetarchive.get_forum("GratefulDead", config_file=TEST_CONFIG)
    assert isinstance(forum, forums.Forum)
    assert forum.identifier == "GratefulDead"


@responses.activate
def test_create_forum_dry_run():
    fields = _backend().create_forum("mycoll", "Name", None, "0", "0", dry_run=True)
    assert fields["action"] == "create"
    assert fields["forumid"] == "mycoll"
    assert len(responses.calls) == 0
