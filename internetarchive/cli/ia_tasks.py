"""
ia_tasks.py

'ia' subcommand for retrieving information about archive.org catalog tasks.
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

import argparse
import sys
import warnings

from requests.exceptions import RequestException

from internetarchive.cli.cli_utils import PostDataAction, QueryStringAction
from internetarchive.utils import json


def setup(subparsers):
    """
    Setup args for tasks command.

    Args:
        subparsers: subparser object passed from ia.py
    """
    parser = subparsers.add_parser("tasks",
                                   aliases=["ta"],
                                   help="Retrieve information about your archive.org catalog tasks")

    parser.add_argument("-t", "--task",
                        nargs="*",
                        help="Return information about the given task.")
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument("-G", "--get-task-log",
                           help="Return the given tasks task log.")
    log_group.add_argument("-f", "--follow-task-log",
                           help="Follow the given task's log as it grows "
                                "(tail -f style); stops when the task finishes.")
    parser.add_argument("-p", "--parameter",
                        nargs=1,
                        action=QueryStringAction,
                        default=None,
                        metavar="KEY:VALUE",
                        help="URL parameters passed to catalog.php. "
                             "Can be specified multiple times.")
    parser.add_argument("-T", "--tab-output",
                        action="store_true",
                        help="Output task info in tab-delimited columns.")
    parser.add_argument("-c", "--cmd",
                        type=str,
                        help="The task to submit (e.g., make_dark.php).")
    parser.add_argument("-C", "--comment",
                        type=str,
                        help="A reasonable explanation for why a task is being submitted.")
    parser.add_argument("-a", "--task-args",
                        nargs=1,
                        action=QueryStringAction,
                        default=None,
                        metavar="KEY:VALUE",
                        help="Args to submit to the Tasks API. "
                             "Can be specified multiple times.")
    parser.add_argument("-d", "--data",
                        nargs=1,
                        action=PostDataAction,
                        metavar="DATA",
                        default=None,
                        help="Additional data to send when submitting a task. "
                             "Accepts 'key:value', 'key=value', or a JSON object. "
                             "Can be specified multiple times.")
    parser.add_argument("-r", "--reduced-priority",
                        action="store_true",
                        help="Submit task at a reduced priority.")
    parser.add_argument("-l", "--get-rate-limit",
                        action="store_true",
                        help="Get rate limit info.")
    parser.add_argument("identifier",
                        type=str,
                        nargs="?",
                        help="Identifier for tasks specific operations.")

    parser.set_defaults(func=lambda args: main(args, parser))


def handle_task_submission_result(result, cmd):
    """
    Handle the result of a task submission.
    """
    if result.get("success"):
        task_log_url = result.get("value", {}).get("log")
        print(f"success: {task_log_url}", file=sys.stderr)
    elif "already queued/running" in result.get("error", ""):
        print(f"success: {cmd} task already queued/running", file=sys.stderr)
    else:
        print(f"error: {result.get('error')}", file=sys.stderr)
    sys.exit(0 if result.get("success") else 1)


def main(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    """
    Main entry point for 'ia tasks'.
    """
    args.parameter = args.parameter or {}
    args.task_args = args.task_args or {}
    args.data = args.data or {}

    # Tasks write API.
    if args.cmd:
        if args.get_rate_limit:
            r = args.session.get_tasks_api_rate_limit(args.cmd)
            print(json.dumps(r))
            sys.exit(0)
        args.data["args"] = args.task_args
        r = args.session.submit_task(args.identifier,
                                     args.cmd,
                                     comment=args.comment,
                                     priority=int(args.data.get("priority", 0)),
                                     reduced_priority=args.reduced_priority,
                                     data=args.data)
        handle_task_submission_result(r.json(), args.cmd)
        sys.exit(0)

    # A positional identifier selects a metadata query and would silently
    # shadow -G/-f (which take their own task id), so reject the combination.
    if args.identifier and (args.get_task_log or args.follow_task_log):
        parser.error("argument identifier: not allowed with "
                     "-G/--get-task-log or -f/--follow-task-log")

    # Tasks read API.
    if args.identifier:
        _params = {"identifier": args.identifier, "catalog": 1, "history": 1}
        _params.update(args.parameter)
        args.parameter = _params
    elif args.get_task_log:
        log = args.session.get_task_log(args.get_task_log, params=args.parameter)
        print(log.encode("utf-8", errors="surrogateescape")
                 .decode("utf-8", errors="replace"))
        sys.exit(0)
    elif args.follow_task_log:
        # ``lines`` keeps Tasks API semantics (negative N = the last N lines)
        # but is applied client-side and never forwarded to the server, which
        # would truncate the body and break delta tracking. A positive value
        # selects the head of the log, which can't be followed, so reject it.
        # Every other -p param is forwarded to each request.
        raw_lines = args.parameter.get("lines")
        lines = None
        if raw_lines is not None:
            try:
                lines = int(raw_lines)
            except (TypeError, ValueError):
                print(f"error: lines must be an integer, got {raw_lines!r}",
                      file=sys.stderr)
                sys.exit(1)
            if lines > 0:
                print("error: --follow-task-log: 'lines' must be negative "
                      "(the last N lines, e.g. -p lines=-20); a positive value "
                      "selects the head of the log, which can't be followed",
                      file=sys.stderr)
                sys.exit(1)
        params = {k: v for k, v in args.parameter.items()
                  if k != "lines"} or None
        # An unknown task id makes the Tasks API return an empty 200 body, so
        # the follower would stream nothing and exit 0 -- misleading. Verify
        # the task exists first so a bad id fails fast with a clear message.
        tid = args.follow_task_log
        try:
            found = any(
                str(getattr(t, "task_id", "")) == str(tid)
                for t in args.session.get_tasks(
                    params={"task_id": tid, "catalog": 1,
                            "history": 1, "summary": 0}))
            if not found:
                print(f"error: task {tid} not found", file=sys.stderr)
                sys.exit(1)
            for chunk in args.session.follow_task_log(tid, lines=lines,
                                                      params=params):
                sys.stdout.write(
                    chunk.encode("utf-8", errors="surrogateescape")
                         .decode("utf-8", errors="replace"))
                sys.stdout.flush()
        except KeyboardInterrupt:
            pass
        except RequestException as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    queryable_params = [
        "identifier",
        "task_id",
        "server",
        "cmd",
        "args",
        "submitter",
        "priority",
        "wait_admin",
        "submittime",
    ]

    if not (args.identifier
            or args.parameter.get("task_id")):
        _params = {"catalog": 1, "history": 0}
        _params.update(args.parameter)
        args.parameter = _params

    if not any(x in args.parameter for x in queryable_params):
        _params = {"submitter": args.session.user_email, "catalog": 1, "history": 0, "summary": 0}
        _params.update(args.parameter)
        args.parameter = _params

    if args.tab_output:
        warn_msg = ("tab-delimited output will be removed in a future release. "
                    "Please switch to the default JSON output.")
        warnings.warn(warn_msg, stacklevel=2)
    for t in args.session.get_tasks(params=args.parameter):
        # Legacy support for tab-delimited output.
        # Mypy is confused by CatalogTask members being created from kwargs
        if args.tab_output:
            color = t.color if t.color else "done"
            task_args = "\t".join([f"{k}={v}" for k, v in t.args.items()])  # type: ignore
            output = "\t".join([str(x) for x in [
                t.identifier,
                t.task_id,
                t.server,
                t.submittime,
                t.cmd,
                color,
                t.submitter,
                task_args,
            ] if x])
            print(output, flush=True)
        else:
            print(t.json(), flush=True)
