"""
ia_forum.py

'ia' subcommand for reading and writing collection forums on archive.org.
"""

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

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from internetarchive import forums
from internetarchive.exceptions import AuthenticationError, ForumError

VERBS = {"list", "read", "post", "reply", "edit", "create"}


def insert_default_verb(argv: list[str]) -> list[str]:
    """Insert the ``list`` verb when ``ia forum`` is given a bare identifier.

    ``ia forum GratefulDead`` is a shortcut for ``ia forum list
    GratefulDead``: if the token following ``forum`` is neither a verb nor
    a flag, ``list`` is inserted. For a collection whose identifier is
    itself a verb name, use the explicit form (``ia forum list list``).

    :param argv: The argument vector, excluding the program name.
    :returns: The (possibly modified) argument vector.
    """
    try:
        i = argv.index("forum")
    except ValueError:
        return argv
    nxt = i + 1
    if nxt < len(argv) and argv[nxt] not in VERBS and not argv[nxt].startswith("-"):
        return argv[:nxt] + ["list"] + argv[nxt:]
    return argv


def setup(subparsers):
    """Set up argument parser for the 'forum' subcommand.

    Args:
        subparsers: argparse subparsers object from main CLI
    """
    parser = subparsers.add_parser(
        "forum",
        help="Read and write collection forums",
        description=(
            "Read and write collection forums. A forum's identifier is the "
            "identifier of the collection it belongs to. 'ia forum "
            "<identifier>' is a shortcut for 'ia forum list <identifier>'."
        ),
    )
    verbs = parser.add_subparsers(
        title="verbs", dest="verb", metavar="{list,read,post,reply,edit,create}"
    )
    verbs.required = True

    list_parser = verbs.add_parser(
        "list",
        help="List recent threads in a forum",
        description=(
            "List recent threads in a forum. The current backend returns a "
            "recent-activity window, not the forum's full history."
        ),
    )
    list_parser.add_argument("identifier", help="Forum (= collection) identifier")
    list_parser.add_argument(
        "--json", action="store_true", help="Output one JSON object per thread"
    )

    read_parser = verbs.add_parser(
        "read",
        help="Read a thread and all of its posts",
    )
    read_parser.add_argument("thread_id", help="Thread id (= the root post's id)")
    read_parser.add_argument(
        "--json", action="store_true", help="Output the thread as JSON"
    )

    post_parser = verbs.add_parser(
        "post",
        help="Post a new thread to a forum",
    )
    post_parser.add_argument("identifier", help="Forum (= collection) identifier")
    post_parser.add_argument("--subject", required=True, help="Post subject")
    _add_body_args(post_parser)
    _add_dry_run(post_parser)

    reply_parser = verbs.add_parser(
        "reply",
        help="Reply to a thread (or a specific post in it)",
    )
    reply_parser.add_argument("thread_id", help="Thread id (= the root post's id)")
    reply_parser.add_argument(
        "--subject", help="Reply subject (default: Re: <thread subject>)"
    )
    reply_parser.add_argument(
        "--parent",
        metavar="POST_ID",
        help="The post being replied to (default: the thread root)",
    )
    _add_body_args(reply_parser)
    _add_dry_run(reply_parser)

    edit_parser = verbs.add_parser(
        "edit",
        help="Edit one of your own posts",
    )
    edit_parser.add_argument("post_id", help="Id of the post to edit")
    edit_parser.add_argument(
        "--thread", required=True, metavar="THREAD_ID", help="Id of the thread"
    )
    edit_parser.add_argument("--subject", required=True, help="New subject")
    _add_body_args(edit_parser)
    _add_dry_run(edit_parser)

    create_parser = verbs.add_parser(
        "create",
        help="Create a forum for a collection (requires special privileges)",
        description=(
            "Create a forum for a collection. Forum creation is "
            "privilege-gated on archive.org; most accounts cannot do it. "
            "Nothing else in 'ia' ever creates a forum implicitly."
        ),
    )
    create_parser.add_argument("identifier", help="Collection identifier")
    create_parser.add_argument("--name", required=True, help="Forum name")
    create_parser.add_argument(
        "--home",
        help="Forum home page path (e.g. /details/<identifier>?tab=forum)",
    )
    create_parser.add_argument(
        "--read-perm",
        default="0",
        metavar="PERM",
        help='Read permission: "0" for everyone, or a privilege path '
        'like "/texts" (default: %(default)s)',
    )
    create_parser.add_argument(
        "--write-perm",
        default="0",
        metavar="PERM",
        help='Write permission; same semantics as --read-perm (default: %(default)s)',
    )
    _add_dry_run(create_parser)

    parser.set_defaults(func=lambda args: main(args, parser))


def _add_body_args(parser: argparse.ArgumentParser) -> None:
    """Add the mutually exclusive --body/--body-file arguments."""
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--body", help="Body text")
    group.add_argument(
        "--body-file",
        metavar="FILE",
        help="Read body text from a file ('-' for stdin)",
    )


def _add_dry_run(parser: argparse.ArgumentParser) -> None:
    """Add the --dry-run argument."""
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be submitted without submitting anything",
    )


def _get_body(args: argparse.Namespace) -> str:
    """Resolve the body text from --body or --body-file."""
    if args.body is not None:
        return args.body
    if args.body_file == "-":
        return sys.stdin.read()
    with open(args.body_file) as fh:
        return fh.read()


def _json_default(obj):
    """JSON encoder default for dataclass field values (datetimes)."""
    return obj.isoformat()


def _print_dry_run(fields: dict) -> None:
    """Print the would-be POST fields of a dry run."""
    print("dry run -- would submit these fields (nothing sent):")
    for key, value in fields.items():
        value = str(value)
        if len(value) > 60:
            value = value[:60] + "..."
        print(f"  {key:12} = {value}")


def _print_recent_threads(forum: forums.Forum) -> None:
    """Print recent thread subjects, verifying a write landed."""
    print("recent threads on this forum:")
    for thread in forum.threads()[:5]:
        print(f"  {thread.id}  {thread.subject}")


def _print_thread(thread: forums.ForumThread) -> None:
    """Print a thread with posts indented by nesting depth."""
    for post in thread.posts:
        indent = "  " * post.depth
        date = post.date.strftime("%b %-d, %Y %-I:%M%p").lower()
        print(f"{indent}[{post.id}] {post.poster} -- {date}")
        print(f"{indent}{post.subject}")
        print()
        for line in post.body.splitlines():
            print(f"{indent}{line}")
        print()


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """Handle forum subcommand execution.

    Args:
        args: Parsed command-line arguments
        parser: Argument parser for error handling
    """
    try:
        _dispatch(args)
    except (ForumError, AuthenticationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


def _dispatch(args: argparse.Namespace) -> None:
    """Route a parsed forum command to the library."""
    session = args.session

    if args.verb == "list":
        forum = session.get_forum(args.identifier)
        threads = forum.threads()
        if args.json:
            for thread in threads:
                print(json.dumps(dataclasses.asdict(thread), default=_json_default))
        else:
            for t in threads:
                date = t.last_post_date.strftime("%b %d %Y %H:%M")
                print(f"{t.id:>10}  {t.poster:<24} {t.replies:>4}  {date}  {t.subject}")
        return

    if args.verb == "read":
        thread = forums.get_thread(session, args.thread_id)
        if args.json:
            print(json.dumps(dataclasses.asdict(thread), default=_json_default))
        else:
            _print_thread(thread)
        return

    if args.verb == "post":
        forum = session.get_forum(args.identifier)
        result = forum.post(args.subject, _get_body(args), dry_run=args.dry_run)
        if args.dry_run:
            _print_dry_run(result)
        else:
            print(f"success: posted to forum '{args.identifier}'")
            _print_recent_threads(forum)
        return

    if args.verb == "reply":
        # One fetch resolves the forum, the default subject, and verifies
        # the thread exists.
        thread = forums.get_thread(session, args.thread_id)
        forum = session.get_forum(thread.forum_id)
        subject = args.subject
        if subject is None:
            subject = (
                thread.subject
                if thread.subject.startswith("Re:")
                else f"Re: {thread.subject}"
            )
        result = forum.reply(
            args.thread_id,
            _get_body(args),
            subject=subject,
            parent_id=args.parent,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            _print_dry_run(result)
        else:
            print(f"success: replied to thread {args.thread_id}")
            _print_recent_threads(forum)
        return

    if args.verb == "edit":
        thread = forums.get_thread(session, args.thread)
        forum = session.get_forum(thread.forum_id)
        result = forum.edit(
            args.post_id,
            args.thread,
            args.subject,
            _get_body(args),
            dry_run=args.dry_run,
        )
        if args.dry_run:
            _print_dry_run(result)
        else:
            print(f"success: edited post {args.post_id}")
        return

    if args.verb == "create":
        forum = session.get_forum(args.identifier)
        result = forum.create(
            args.name,
            home=args.home,
            public_read=args.read_perm,
            public_write=args.write_perm,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            _print_dry_run(result)
        else:
            print(f"success: created forum '{args.identifier}'")
        return
