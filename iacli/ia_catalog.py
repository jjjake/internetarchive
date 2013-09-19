"""Retrieve information about your catalog tasks.

usage: 
    ia catalog [--help] [options...]

options:
    -h, --help
    -v, --verbose       
    -u, --url=<url>             ...
    -g, --green-rows            Return information about tasks that have not run.
    -b, --blue-rows             Return information about running tasks.
    -r, --red-rows              Return information about tasks that have failed.
    -f , --fields <field>...    Return only the specified fields. <field> may be one
                                of the following: 
                                
                                identifier, server, command, time, submitter, args, 
                                task_id, row_type
"""
from docopt import docopt
import sys
import urlparse

import internetarchive



# ia_catalog()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    if args['--url']:
        parsed_url = urlparse.urlparse(args['--url'][0])
        params = urlparse.parse_qs(parsed_url.query)
        c = internetarchive.Catalog(params=params)
    else:
        c = internetarchive.Catalog()
    row_types = {
            c.GREEN: 'green',
            c.BLUE: 'blue',
            c.RED: 'red',
            c.BROWN: 'brown',
    }
    if args['--green-rows']:
        tasks = c.green_rows
    elif args['--blue-rows']:
        tasks = c.blue_rows
    elif args['--red-rows']:
        tasks = c.red_rows
    else:
        tasks = c.tasks
    for t in tasks:
        if args['--fields']:
            task_info = []
            for field in args['--fields']:
                info = eval('t.{0}'.format(field))
                task_info.append(info)
        else:
            task_info = [
                    t.identifier, t.task_id, t.server, t.time, t.command, 
                    row_types[t.row_type]
            ]
            if args['--verbose']:
                targs = '\t'.join(['{0}={1}'.format(k, v) for (k,v) in t.args.items()])
                task_info += [t.submitter, targs]
        sys.stdout.write('\t'.join([str(x) for x in task_info]) + '\n')
    sys.exit(0)
