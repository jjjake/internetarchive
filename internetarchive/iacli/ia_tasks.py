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
import sys

from docopt import docopt

from internetarchive import Catalog, get_tasks
from internetarchive.iacli.argparser import get_args_dict


# ia_catalog()
#_________________________________________________________________________________________
def main(argv):
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
        if args['<identifier>']:
            tasks = get_tasks(identifier=args['<identifier>'], task_type=task_type, params=params)
        elif args['--get-task-log']:
            task = get_tasks(task_ids=args['--get-task-log'], params=params)
            if task:
                log = task[0].task_log()
                sys.stdout.write(log)
            else:
                sys.stderr.write(
                    'error retrieving task-log for {0}\n'.format(args['--get-task-log'])
                )
                sys.exit(1)
            sys.exit(0)
        elif args['--task']:
            tasks = get_tasks(task_ids=args['--task'], params=params)
        else:
            tasks = get_tasks(task_type=task_type, params=params)

        for t in tasks:
            task_info = [
                t.identifier, t.task_id, t.server, t.time, t.command, 
                row_types[t.row_type],
            ]
            if args['--verbose']:
                # parse task args and append to task_info list.
                targs = '\t'.join(['{0}={1}'.format(k, v) for (k, v) in t.args.items()])
                task_info += [t.submitter, targs]
            sys.stdout.write('\t'.join([str(x) for x in task_info]) + '\n')
    except NameError as exc:
        sys.stderr.write('error: {0}'.format(exc.message))
        sys.exit(1)
