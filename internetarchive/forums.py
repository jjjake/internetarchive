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
internetarchive.forums
~~~~~~~~~~~~~~~~~~~~~~

Read and write Archive.org collection forums.

A forum's identifier is the identifier of the collection it belongs to
(e.g. ``GratefulDead``). Threads and posts have their own numeric ids;
a thread id is the id of its root post.

There is no supported forum API yet, so this module is currently backed
by the legacy ``/iathreads/`` pages and the Offshoot listing service via
the private :class:`_IathreadsBackend`. The public surface —
:class:`Forum`, :func:`get_thread`, and the dataclasses — is designed to
stay stable when a proper API replaces that backend.

:copyright: (C) 2012-2026 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""

from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from internetarchive.exceptions import (
    AuthenticationError,
    ForumError,
    ForumNotFoundError,
)

__all__ = ["Forum", "ForumPost", "ForumThread", "ThreadSummary", "get_thread"]


@dataclass(frozen=True)
class ThreadSummary:
    """One thread in a forum listing.

    :param id: Thread id (the root post's id), e.g. ``"2445301"``.
    :param subject: Subject of the root post.
    :param poster: Screen name of the root poster.
    :param replies: Number of replies to the root post.
    :param date: When the root post was made (site-local, naive).
    :param last_post_date: Most recent activity in the thread (site-local,
        naive); equals ``date`` when there are no replies in the listing.
    """

    id: str
    subject: str
    poster: str
    replies: int
    date: datetime
    last_post_date: datetime


@dataclass(frozen=True)
class ForumPost:
    """A single post within a forum thread.

    :param id: Post id.
    :param thread_id: Id of the thread this post belongs to.
    :param parent_id: Id of the post this replies to; ``None`` for the root.
    :param depth: Nesting depth; ``0`` for the thread root.
    :param poster: Screen name of the poster.
    :param date: When the post was made (site-local, naive).
    :param subject: Post subject.
    :param body: Post body as plain text (tags stripped, entities unescaped).
    :param body_html: Post body as raw HTML.
    """

    id: str
    thread_id: str
    parent_id: str | None
    depth: int
    poster: str
    date: datetime
    subject: str
    body: str
    body_html: str


@dataclass(frozen=True)
class ForumThread:
    """A forum thread: the root post and all replies.

    :param id: Thread id (the root post's id).
    :param forum_id: Identifier of the forum (= collection identifier).
    :param subject: Subject of the root post.
    :param posts: All posts in document order; ``depth`` gives the tree.
    """

    id: str
    forum_id: str
    subject: str
    posts: list[ForumPost]


# ---------------------------------------------------------------------------
# Parsers for the legacy iathreads pages. Everything below is private and
# disposable: it exists only until a proper forum API replaces the backend.
# ---------------------------------------------------------------------------

_LISTING_ROW_RE = re.compile(r'<tr valign="top"\s+class="(?:eve|odd) forumRow">')
_POST_LINK_RE = re.compile(r'<a href="/post/(\d+)">\s*(.*?)\s*</a>', re.S)
_POSTER_LINK_RE = re.compile(r'poster=[^"]*"\s*>\s*(.*?)\s*</a>', re.S)
_COUNT_CELL_RE = re.compile(r"<td>\s*(\d+)\s*</td>")
_DATE_CELL_RE = re.compile(r"<nobr[^>]*>([^<]+)</nobr>")
_POST_BOX_MARKER = '<div class="box well well-sm"'
_REPLY_LINK_RE = re.compile(
    r"reply=1&(?:amp;)?parentid=(\d+)&(?:amp;)?threadid=(\d+)&(?:amp;)?nested=(\d+)"
)
_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.I)


def _parse_date(text: str) -> datetime:
    """Parse a forum timestamp like ``Jul 23, 2026 7:26am``.

    :param text: The timestamp text as rendered by the forum pages.
    :returns: A naive :class:`datetime.datetime` (site-local time).
    """
    return datetime.strptime(text.strip(), "%b %d, %Y %I:%M%p")


def _clean(text: str) -> str:
    """Strip tags, unescape entities, and collapse whitespace."""
    return " ".join(html_lib.unescape(_TAG_RE.sub("", text)).split())


def _parse_listing(listing_html: str) -> list[ThreadSummary]:
    """Parse the Offshoot forum listing table into thread summaries.

    Reply rows (indented with ``&nbsp;``) follow their thread root in the
    table; they only contribute to ``last_post_date``.

    :param listing_html: The ``value.html`` payload from Offshoot.
    :returns: Thread summaries in listing order.
    :raises ForumError: If a row cannot be parsed.
    """
    rows = _LISTING_ROW_RE.split(listing_html)[1:]
    threads: list[dict] = []
    for row in rows:
        link = _POST_LINK_RE.search(row)
        poster = _POSTER_LINK_RE.search(row)
        count = _COUNT_CELL_RE.search(row)
        date_cell = _DATE_CELL_RE.search(row)
        if not (link and poster and count and date_cell):
            raise ForumError(
                "could not parse a forum listing row -- the page format may "
                "have changed; please report this at "
                "https://github.com/jjjake/internetarchive/issues"
            )
        date = _parse_date(date_cell.group(1))
        is_reply = "&nbsp;" in row.split("<a", 1)[0]
        if is_reply:
            if threads and date > threads[-1]["last_post_date"]:
                threads[-1]["last_post_date"] = date
            continue
        threads.append(
            {
                "id": link.group(1),
                "subject": _clean(link.group(2)),
                "poster": _clean(poster.group(1)),
                "replies": int(count.group(1)),
                "date": date,
                "last_post_date": date,
            }
        )
    return [ThreadSummary(**t) for t in threads]


def _field_cell(block: str, label: str) -> str | None:
    """Extract the value cell following a ``<strong>Label:</strong>`` cell."""
    m = re.search(
        rf"<strong>{label}:</strong>\s*</td>\s*<td[^>]*>(.*?)</td>", block, re.S
    )
    return _clean(m.group(1)) if m else None


def _parse_post_block(block: str, parents: dict[int, str]) -> ForumPost:
    """Parse one ``div.box.well.well-sm`` post block from a thread page.

    :param block: The block's HTML (from the box div marker to the next).
    :param parents: Mutable map of depth -> most recent post id at that
        depth, used to derive ``parent_id``; updated in place.
    :raises ForumError: If the block cannot be parsed.
    """
    reply_link = _REPLY_LINK_RE.search(block)
    poster = _field_cell(block, "Poster")
    date = _field_cell(block, "Date")
    subject = _field_cell(block, "Subject")
    if not (reply_link and poster and date and subject) or "</h2>" not in block:
        raise ForumError(
            "could not parse a forum post -- the page format may have "
            "changed; please report this at "
            "https://github.com/jjjake/internetarchive/issues"
        )
    post_id, thread_id, nested = reply_link.groups()
    depth = int(nested) - 1
    parents[depth] = post_id
    body_html = block.split("</h2>", 1)[1]
    body_html = body_html.split("<!--/.container-->")[0]
    # The trailing </div>s close the post box (and, on the last post of the
    # page, its containers). A body that itself ends with a closing div
    # would lose it here -- an accepted limitation of this scrape.
    body_html = re.sub(r"(\s*</div>)+\s*$", "", body_html).strip()
    body = html_lib.unescape(_TAG_RE.sub("", _BR_RE.sub("\n", body_html))).strip()
    return ForumPost(
        id=post_id,
        thread_id=thread_id,
        parent_id=parents.get(depth - 1) if depth > 0 else None,
        depth=depth,
        poster=poster,
        date=_parse_date(date),
        subject=subject,
        body=body,
        body_html=body_html,
    )


def _parse_thread(page_html: str) -> ForumThread:
    """Parse a ``/post/<thread-id>`` page into a :class:`ForumThread`.

    :param page_html: The full thread page HTML.
    :raises ForumError: If no posts can be parsed from the page.
    """
    blocks = page_html.split(_POST_BOX_MARKER)[1:]
    parents: dict[int, str] = {}
    posts = [_parse_post_block(b, parents) for b in blocks]
    if not posts:
        raise ForumError(
            "no posts found on the thread page -- the page format may have "
            "changed; please report this at "
            "https://github.com/jjjake/internetarchive/issues"
        )
    root = posts[0]
    m = re.search(r'href="/details/([^"?]+)\?tab=forum"', page_html)
    forum_id = m.group(1) if m else ""
    return ForumThread(
        id=root.thread_id, forum_id=forum_id, subject=root.subject, posts=posts
    )


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

_OFFSHOOT_PATH = "/services/offshoot/forum-posts.php"
_POST_PAGE_PATH = "/post"
_POST_NEW_PATH = "/iathreads/post-new.php"
_FORUM_NEW_PATH = "/iathreads/forum-new.php"
_TITLE_RE = re.compile(r"<title>([^<]*)</title>")


def _page_title(page_html: str) -> str:
    """Return the stripped ``<title>`` of a page, or ``""``."""
    m = _TITLE_RE.search(page_html)
    return m.group(1).strip() if m else ""


class _IathreadsBackend:
    """Client for the legacy iathreads pages and the Offshoot listing.

    Private and disposable: when a proper forum API ships, a replacement
    backend with the same method signatures slots in behind
    :class:`Forum` and this class (plus the parsers above) is deleted.

    :param archive_session: An :class:`ArchiveSession
        <internetarchive.session.ArchiveSession>` object.
    """

    def __init__(self, archive_session):
        self.session = archive_session
        self.base_url = f"{archive_session.protocol}//{archive_session.host}"

    # -- reads --------------------------------------------------------------

    def _offshoot(self, forum_id: str) -> dict:
        """Fetch the Offshoot listing envelope for ``forum_id``.

        :returns: The ``value`` object (``{"exists": bool, "html": ...}``).
        :raises ForumError: If the envelope reports failure.
        """
        r = self.session.get(
            f"{self.base_url}{_OFFSHOOT_PATH}",
            params={"forum_id": forum_id},
            timeout=30,
        )
        j = r.json()
        if not j.get("success"):
            raise ForumError(f"forum listing failed: {j.get('error', r.text[:200])}")
        return j["value"]

    def exists(self, forum_id: str) -> bool:
        """Return whether a forum exists for ``forum_id``."""
        return bool(self._offshoot(forum_id).get("exists"))

    def list_posts(self, forum_id: str) -> list[ThreadSummary]:
        """List recent threads in a forum.

        The current backend returns a recent-activity window (roughly the
        last 150 posts), not the forum's full history.

        :raises ForumNotFoundError: If the forum does not exist.
        :raises ForumError: If the listing cannot be parsed.
        """
        value = self._offshoot(forum_id)
        if not value.get("exists"):
            raise ForumNotFoundError(
                f"forum '{forum_id}' does not exist -- forums are created "
                "per collection; see 'ia forum create'"
            )
        listing_html = value.get("html") or ""
        if "forumRow" not in listing_html:
            raise ForumError(
                "no forum table found in the listing -- the page format "
                "may have changed; please report this at "
                "https://github.com/jjjake/internetarchive/issues"
            )
        return _parse_listing(listing_html)

    def get_thread(self, thread_id: str) -> ForumThread:
        """Fetch and parse a thread page.

        :raises ForumNotFoundError: If the thread does not exist.
        :raises ForumError: If the page cannot be parsed.
        """
        r = self.session.get(
            f"{self.base_url}{_POST_PAGE_PATH}/{thread_id}", timeout=30
        )
        if r.status_code == 404:
            raise ForumNotFoundError(f"thread '{thread_id}' does not exist")
        r.raise_for_status()
        if _POST_BOX_MARKER not in r.text:
            raise ForumError(
                "no posts found on the thread page -- the page format may "
                "have changed; please report this at "
                "https://github.com/jjjake/internetarchive/issues"
            )
        return _parse_thread(r.text)

    # -- writes ---------------------------------------------------------------
    #
    # Writing goes through the same form the browser uses: GET the compose
    # form (which sets an HttpOnly `ia-csrf` cookie and embeds a JWT whose
    # nonce claim must match it -- a double-submit check), then POST the
    # form back as multipart/form-data. The `submit` field must be
    # "Submit Post": the form has a second "Add Files" submit button that
    # fails silently. (Validator: petabox www/common/Auth.inc.)

    def _require_auth(self) -> None:
        """Fail fast when the session carries no archive.org login cookies.

        :raises AuthenticationError: If `logged-in-user`/`logged-in-sig`
            cookies are absent from the session.
        """
        names = {c.name for c in self.session.cookies}
        if not {"logged-in-user", "logged-in-sig"} <= names:
            raise AuthenticationError(
                "forum writes require your archive.org login cookies "
                "(logged-in-user/logged-in-sig) -- run 'ia configure' first"
            )

    def _fetch_form(self, form_url: str, forum_id: str | None) -> dict:
        """GET a compose/reply/edit form and scrape the fields to echo back.

        The GET also lands the `ia-csrf` cookie in the session jar, which
        the subsequent POST must carry.

        :param form_url: The post-new.php URL for this operation.
        :param forum_id: Forum identifier, used to disambiguate a missing
            csrf token (nonexistent forum vs. stale login); may be ``None``
            when the operation doesn't know the forum (never the case
            today, but tolerated).
        :returns: ``{"csrf_token": ..., "date": ...}``.
        :raises ForumNotFoundError: If the forum does not exist.
        :raises AuthenticationError: If the form has no csrf token but the
            forum exists (missing or stale login cookies).
        """
        r = self.session.get(form_url, timeout=30)

        def val(name: str) -> str | None:
            m = re.search(rf'name="{name}"[^>]*value="([^"]*)"', r.text)
            return html_lib.unescape(m.group(1)) if m else None

        csrf_token, date = val("csrf_token"), val("date")
        if not csrf_token or not date:
            if forum_id is not None and not self.exists(forum_id):
                raise ForumNotFoundError(
                    f"forum '{forum_id}' does not exist -- forums are "
                    "created per collection; see 'ia forum create'"
                )
            raise AuthenticationError(
                "could not scrape csrf_token/date from the compose form -- "
                "your login cookies may be missing or stale; run "
                "'ia configure'"
            )
        return {"csrf_token": csrf_token, "date": date}

    def _submit(
        self,
        form_url: str,
        forum_id: str,
        subject: str,
        body: str,
        extra: dict,
        dry_run: bool,
        success_marker: str = "Successful",
    ) -> dict | None:
        """Run the form round-trip shared by post/reply/edit.

        :param extra: Operation-specific POST fields.
        :param dry_run: If true, fetch the form but return the would-be
            POST fields instead of posting.
        :returns: The field dict when ``dry_run``, else ``None``.
        :raises ForumError: If the response page does not signal success.
        """
        self._require_auth()
        scraped = self._fetch_form(form_url, forum_id)
        fields = {
            "date": scraped["date"],
            "postsubject": subject,
            "postbody": body,
            "forum": forum_id,
            "csrf_token": scraped["csrf_token"],
            "referer": "",
            **extra,
            "submit": "Submit Post",
        }
        if dry_run:
            return fields
        r = self.session.post(
            f"{self.base_url}{_POST_NEW_PATH}",
            files={k: (None, str(v)) for k, v in fields.items()},
            timeout=60,
        )
        title = _page_title(r.text)
        if success_marker not in title:
            raise ForumError(
                f"post rejected (response title: {title!r}) -- usual "
                "causes: wrong forum id, editing a post that isn't yours, "
                "or a stale form (each attempt fetches a fresh token)"
            )
        return None

    def submit_post(
        self, forum_id: str, subject: str, body: str, dry_run: bool = False
    ) -> dict | None:
        """Post a new thread to a forum.

        :returns: The would-be POST fields when ``dry_run``, else ``None``.
        """
        form_url = f"{self.base_url}{_POST_NEW_PATH}?forum={quote(forum_id)}"
        return self._submit(form_url, forum_id, subject, body, {}, dry_run)

    def submit_reply(
        self,
        forum_id: str,
        thread_id: str,
        parent_id: str,
        subject: str,
        body: str,
        dry_run: bool = False,
    ) -> dict | None:
        """Reply to a post in a thread.

        :param parent_id: The post being replied to (the thread id itself
            when replying to the root).
        :returns: The would-be POST fields when ``dry_run``, else ``None``.
        """
        form_url = (
            f"{self.base_url}{_POST_NEW_PATH}?reply=1"
            f"&parentid={quote(parent_id)}&threadid={quote(thread_id)}"
            f"&nested=1&subject={quote(subject)}&forum={quote(forum_id)}"
        )
        extra = {"parentid": parent_id, "threadid": thread_id, "nested": "1"}
        return self._submit(form_url, forum_id, subject, body, extra, dry_run)

    def submit_edit(
        self,
        forum_id: str,
        post_id: str,
        thread_id: str,
        subject: str,
        body: str,
        dry_run: bool = False,
    ) -> dict | None:
        """Edit one of your own posts.

        :returns: The would-be POST fields when ``dry_run``, else ``None``.
        """
        form_url = (
            f"{self.base_url}{_POST_NEW_PATH}?action=edit"
            f"&id={quote(post_id)}&threadid={quote(thread_id)}"
        )
        extra = {"action": "edit", "id": post_id, "threadid": thread_id}
        return self._submit(
            form_url,
            forum_id,
            subject,
            body,
            extra,
            dry_run,
            success_marker="modification Successful",
        )

    def create_forum(
        self,
        forum_id: str,
        name: str,
        home: str | None,
        public_read: str,
        public_write: str,
        dry_run: bool = False,
    ) -> dict | None:
        """Create a forum for a collection. Explicit operation only.

        Unlike posting, the create form has no csrf token; it is a plain
        urlencoded POST gated server-side by account privileges. Because
        the response page shape is unverified, success is confirmed with a
        follow-up Offshoot existence read rather than trusted.

        :returns: The would-be POST fields when ``dry_run``, else ``None``.
        :raises AuthenticationError: If the server rejects the request
            (401/403) -- creating forums requires special privileges.
        :raises ForumError: If the forum does not exist after the POST.
        """
        fields = {
            "action": "create",
            "referer": "",
            "forumid": forum_id,
            "forumname": name,
            "forumhome": home or "",
            "public_read": public_read,
            "public_write": public_write,
            "submit": "Create Forum",
        }
        if dry_run:
            return fields
        self._require_auth()
        r = self.session.post(
            f"{self.base_url}{_FORUM_NEW_PATH}", data=fields, timeout=60
        )
        if r.status_code in (401, 403):
            raise AuthenticationError(
                "not authorized to create forums -- forum creation requires "
                "special privileges on archive.org"
            )
        r.raise_for_status()
        if not self.exists(forum_id):
            raise ForumError(
                f"forum '{forum_id}' was not created (the server accepted "
                "the request but the forum still does not exist)"
            )
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class Forum:
    """The forum of an Archive.org collection.

    Construction is cheap -- no requests are made until a method is
    called. Forums are created per collection, so a forum's identifier is
    its collection's identifier and not every collection has one; see
    :meth:`exists` and :meth:`create`.

    Write methods return ``None`` on success and raise on failure (the
    current backend cannot report the new post's id). All write methods
    accept ``dry_run=True``, which performs only safe GET requests and
    returns the exact fields that would have been submitted.

    Usage:
        >>> from internetarchive import get_forum
        >>> forum = get_forum('GratefulDead')
        >>> for thread in forum.threads():
        ...     print(thread.id, thread.subject)

    :param archive_session: An :class:`ArchiveSession
        <internetarchive.session.ArchiveSession>` object.
    :param identifier: The forum identifier (= the collection identifier),
        e.g. ``GratefulDead``.
    """

    def __init__(self, archive_session, identifier: str):
        self.session = archive_session
        self.identifier = identifier
        self._backend = _IathreadsBackend(archive_session)

    def __repr__(self) -> str:
        return f"Forum(identifier={self.identifier!r})"

    def exists(self) -> bool:
        """Return whether this forum exists.

        :returns: ``True`` if the forum exists.
        """
        return self._backend.exists(self.identifier)

    def threads(self) -> list[ThreadSummary]:
        """List recent threads in this forum.

        The current backend returns a recent-activity window (roughly the
        last 150 posts), not the forum's full history.

        :returns: :class:`ThreadSummary` objects in listing order.
        :raises ForumNotFoundError: If the forum does not exist.
        """
        return self._backend.list_posts(self.identifier)

    def thread(self, thread_id: str) -> ForumThread:
        """Fetch a thread and all of its posts.

        :param thread_id: The thread id (= the root post's id).
        :returns: A :class:`ForumThread`.
        :raises ForumNotFoundError: If the thread does not exist.
        """
        return self._backend.get_thread(thread_id)

    def post(self, subject: str, body: str, dry_run: bool = False):
        """Post a new thread to this forum.

        :param subject: The post subject.
        :param body: The post body (plain text).
        :param dry_run: Fetch the compose form but return the would-be
            POST fields instead of posting.
        :returns: ``None`` on success; the field dict when ``dry_run``.
        :raises ForumNotFoundError: If the forum does not exist (forums
            are never created implicitly; see :meth:`create`).
        :raises AuthenticationError: If not logged in.
        :raises ForumError: If the post is rejected.
        """
        return self._backend.submit_post(
            self.identifier, subject, body, dry_run=dry_run
        )

    def reply(
        self,
        thread_id: str,
        body: str,
        subject: str | None = None,
        parent_id: str | None = None,
        dry_run: bool = False,
    ):
        """Reply to a thread (or to a specific post within it).

        :param thread_id: The thread id (= the root post's id).
        :param body: The reply body (plain text).
        :param subject: The reply subject; defaults to ``Re: <root
            subject>`` (fetching the thread to learn it).
        :param parent_id: The post being replied to; defaults to the
            thread root.
        :param dry_run: Fetch the forms but return the would-be POST
            fields instead of posting.
        :returns: ``None`` on success; the field dict when ``dry_run``.
        :raises AuthenticationError: If not logged in.
        :raises ForumError: If the reply is rejected.
        """
        if subject is None:
            root_subject = self.thread(thread_id).subject
            if root_subject.startswith("Re:"):
                subject = root_subject
            else:
                subject = f"Re: {root_subject}"
        return self._backend.submit_reply(
            self.identifier,
            thread_id,
            parent_id or thread_id,
            subject,
            body,
            dry_run=dry_run,
        )

    def edit(
        self,
        post_id: str,
        thread_id: str,
        subject: str,
        body: str,
        dry_run: bool = False,
    ):
        """Edit one of your own posts.

        :param post_id: The id of the post to edit.
        :param thread_id: The id of the thread containing the post.
        :param subject: The new subject.
        :param body: The new body (plain text).
        :param dry_run: Fetch the form but return the would-be POST
            fields instead of posting.
        :returns: ``None`` on success; the field dict when ``dry_run``.
        :raises AuthenticationError: If not logged in.
        :raises ForumError: If the edit is rejected (e.g. not your post).
        """
        return self._backend.submit_edit(
            self.identifier, post_id, thread_id, subject, body, dry_run=dry_run
        )

    def create(
        self,
        name: str,
        home: str | None = None,
        public_read: str = "0",
        public_write: str = "0",
        dry_run: bool = False,
    ):
        """Create this forum. An explicit operation -- nothing in this
        library ever creates a forum implicitly.

        Forum creation is privilege-gated server-side; most accounts
        cannot do it.

        :param name: Human-readable forum name, e.g. ``Grateful Dead
            Forum``.
        :param home: Forum home page path, e.g.
            ``/details/<identifier>?tab=forum``.
        :param public_read: Read permission: ``"0"`` for everyone, or a
            privilege path (e.g. ``/texts``) to restrict to those admins.
        :param public_write: Write permission; same semantics.
        :param dry_run: Return the would-be POST fields without posting.
        :returns: ``None`` on success; the field dict when ``dry_run``.
        :raises AuthenticationError: If not logged in or not authorized.
        :raises ForumError: If the forum was not created.
        """
        return self._backend.create_forum(
            self.identifier,
            name,
            home,
            public_read,
            public_write,
            dry_run=dry_run,
        )


def get_thread(archive_session, thread_id: str) -> ForumThread:
    """Fetch a forum thread by id, without knowing its forum.

    The returned thread's ``forum_id`` identifies the forum it belongs
    to, so this is also the way to resolve a bare thread/post id.

    :param archive_session: An :class:`ArchiveSession
        <internetarchive.session.ArchiveSession>` object.
    :param thread_id: The thread id (= the root post's id).
    :returns: A :class:`ForumThread`.
    :raises ForumNotFoundError: If the thread does not exist.
    """
    return _IathreadsBackend(archive_session).get_thread(thread_id)
