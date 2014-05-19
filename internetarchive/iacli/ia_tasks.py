"""Retrieve information about your catalog tasks.

usage:
    ia tasks [--verbose] [--task=<task_id>...] [--get-task-log=<task_id>]
             [--green-rows] [--blue-rows] [--red-rows]
    ia tasks [--verbose] <identifier>
    ia tasks --help

options:
    -h, --help
    -v, --verbose                 Ouptut detailed information for each task.
    -t, --task=<task_id>...       Return information about the given task.
    -G, --get-task-log=<task_id>  Return the given tasks task log.
    -g, --green-rows              Return information about tasks that have not run.
    -b, --blue-rows               Return information about running tasks.
    -r, --red-rows                Return information about tasks that have failed.

"""
import sys

from docopt import docopt

from internetarchive import Catalog, get_tasks


# ia_catalog()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    row_types = {
        -1: 'done',
        0: 'green',
        1: 'blue',
        2: 'red',
        9: 'brown',
    }

    try:
        if args['<identifier>']:
            tasks = get_tasks(identifier=args['<identifier>'])
        elif args['--green-rows']:
            tasks = get_tasks(task_type='green')
        elif args['--blue-rows']:
            tasks = get_tasks(task_type='blue')
        elif args['--red-rows']:
            tasks = get_tasks(task_type='red')
        elif args['--get-task-log']:
            task = get_tasks(task_ids=args['--get-task-log'])
            if task:
                log = task[0].task_log()
                sys.stdout.write(log)
            else:
                sys.stderr.write(
                    'error retrieving task-log for {0}\n'.format(args['--get-task-log'])
                )
                sys.exit(1)
            sys.exit(0)
        else:
            tasks = get_tasks(task_ids=args['--task'])
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
