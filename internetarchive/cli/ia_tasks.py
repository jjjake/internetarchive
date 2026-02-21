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

from requests.exceptions import HTTPError

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
                        metavar="TASK_ID",
                        help="Return information about the given task.")
    parser.add_argument("-G", "--get-task-log",
                        metavar="TASK_ID",
                        help="Return the given tasks task log.")
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
    parser.add_argument("-R", "--rerun",
                        type=int,
                        metavar="TASK_ID",
                        help="Rerun the specified task.")

    parser.set_defaults(func=lambda args: main(args, parser))


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
        j = r.json()
        if j.get("success"):
            task_log_url = j.get("value", {}).get("log")
            print(f"success: {task_log_url}", file=sys.stderr)
        elif "already queued/running" in j.get("error", ""):
            print(f"success: {args.cmd} task already queued/running", file=sys.stderr)
        else:
            print(f"error: {j.get('error')}", file=sys.stderr)
        sys.exit(0 if j.get("success") else 1)
    elif args.rerun:
        if not args.identifier:
            parser.error('The positional argument `identifier` '
                         'is required when using `--rerun`.')
        item = args.session.get_item(args.identifier)
        try:
            r = item.rerun_task(args.rerun)
        except HTTPError as exc:
            if exc.response.status_code == 409:
                print(f"warning: task {args.rerun} "
                      f"for item '{args.identifier}' "
                      "does not need to be reran")
                sys.exit(0)
        j = r.json()
        if j.get("success"):
            print(f"success: Reran task {args.rerun} for item '{args.identifier}'")
        sys.exit(0)

    # Tasks read API.
    if args.identifier:
        _params = {"identifier": args.identifier, "catalog": 1, "history": 1}
        _params.update(args.parameter)
        args.parameter = _params
    elif args.get_task_log:
        log = args.session.get_task_log(args.get_task_log, **args.parameter)
        print(log.encode("utf-8", errors="surrogateescape")
                 .decode("utf-8", errors="replace"))
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
