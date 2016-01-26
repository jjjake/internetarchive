"""Retrieve information about your catalog tasks.

usage:
    ia tasks [--verbose] [--task=<task_id>...] [--get-task-log=<task_id>]
             [--green-rows] [--blue-rows] [--red-rows] [--parameter=<k:v>...]
    ia tasks [--verbose] <identifier>
             [--green-rows] [--blue-rows] [--red-rows] [--parameter=<k:v>...]
    ia tasks --help

options:
    -h, --help
    -v, --verbose                 Ouptut detailed information for each task.
    -t, --task=<task_id>...       Return information about the given task.
    -G, --get-task-log=<task_id>  Return the given tasks task log.
    -g, --green-rows              Return information about tasks that have not run.
    -b, --blue-rows               Return information about running tasks.
    -r, --red-rows                Return information about tasks that have failed.
    -p, --parameter=<k:v>...      Return tasks matching the given parameter.

"""
from __future__ import absolute_import, print_function, unicode_literals
import sys

from docopt import docopt

from internetarchive.cli.argparser import get_args_dict


def main(argv, session):
    args = docopt(__doc__, argv=argv)
    params = get_args_dict(args['--parameter'])

    row_types = {
        -1: 'done',
        0: 'green',
        1: 'blue',
        2: 'red',
        9: 'brown',
    }

    task_type = None
    if args['--green-rows']:
        task_type = 'green'
    elif args['--blue-rows']:
        task_type = 'blue'
    elif args['--red-rows']:
        task_type = 'red'

    try:
        try:
            if args['<identifier>']:
                tasks = session.get_tasks(identifier=args['<identifier>'],
                                          task_type=task_type,
                                          params=params)
            elif args['--get-task-log']:
                task = session.get_tasks(task_ids=args['--get-task-log'], params=params)
                if task:
                    log = task[0].task_log()
                    sys.exit(print(log))
                else:
                    print('error retrieving task-log '
                          'for {0}\n'.format(args['--get-task-log']), file=sys.stderr)
                    sys.exit(1)
            elif args['--task']:
                tasks = session.get_tasks(task_ids=args['--task'], params=params)
            else:
                tasks = session.get_tasks(task_type=task_type, params=params)
        except ValueError as exc:
            print('error: unable to parse JSON. have you run `ia configure`?'.format(exc),
                  file=sys.stderr)
            sys.exit(1)

        for t in tasks:
            task_info = [
                t.identifier, t.task_id, t.server, t.time, t.command,
                row_types[t.row_type],
            ]
            if args['--verbose']:
                # parse task args and append to task_info list.
                targs = '\t'.join(['{0}={1}'.format(k, v) for (k, v) in t.args.items()])
                task_info += [t.submitter, targs]
            print('\t'.join([str(x) for x in task_info]))
    except NameError as exc:
        print('error: {0}'.format(exc.message), file=sys.stderr)
        sys.exit(1)
