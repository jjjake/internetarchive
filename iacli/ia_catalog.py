"""Retrieve information about your catalog tasks.

usage: 
    ia catalog [--verbose] [--url=<url>] [--green-rows] [--blue-rows]
               [--red-rows]
    ia catalog --help

options:
    -h, --help
    -v, --verbose     Ouptut detailed information for each task.
    -g, --green-rows  Return information about tasks that have not run.
    -b, --blue-rows   Return information about running tasks.
    -r, --red-rows    Return information about tasks that have failed.

"""
from sys import stdout, exit
from urlparse import urlparse, parse_qs

from docopt import docopt

from internetarchive import Catalog, get_tasks



# ia_catalog()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    row_types = {
            0: 'green',
            1: 'blue',
            2: 'red',
            9: 'brown',
    }

    if args['--green-rows']:
        tasks = get_tasks(task_type='green')
    elif args['--blue-rows']:
        tasks = get_tasks(task_type='blue')
    elif args['--red-rows']:
        tasks = get_tasks(task_type='red')
    else:
        tasks = c.tasks
    for t in tasks:
        task_info = [
            t.identifier, t.task_id, t.server, t.time, t.command, row_types[t.row_type],
        ]
        if args['--verbose']:
            # parse task args and append to task_info list.
            targs = '\t'.join(['{0}={1}'.format(k, v) for (k,v) in t.args.items()])
            task_info += [t.submitter, targs]
        stdout.write('\t'.join([str(x) for x in task_info]) + '\n')
