"""List files in a given item.

usage:
    ia list [-v] [--glob=<pattern>] [--location] [--source=<source>] 
            [--columns <column1,column2> | --all] <identifier>
    ia metadata --help

options:
    -h, --help
    -v, --verbose               Print column headers. [default: False]
    -a, --all                   List all information available for files.
    -l, --location              Print full URL for each file.
    -c, --columns=<name,size>   List specified file information. [default: name]
    -g, --glob=<pattern>        Only return patterns match the given pattern.
    -s, --source=<source>       Return files matching source.

"""
import sys
import csv
from itertools import chain
from fnmatch import fnmatch
import six

from docopt import docopt

from internetarchive import get_item


# main()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)
    item = get_item(args['<identifier>'])

    files = item.files
    if args.get('--all'):
        columns = list(set(chain.from_iterable(k for k in files)))
    else:
        columns = args['--columns'].split(',')
        if not isinstance(columns, list):
            columns = [columns]

    dict_writer = csv.DictWriter(sys.stdout, columns, delimiter='\t')

    if args.get('--glob'):
        patterns = args['--glob'].split('|')
        if not isinstance(patterns, list):
            patterns = [patterns]
        files = [f for f in files if any(fnmatch(f['name'], p) for p in patterns)]
    elif args.get('--source'):
        files = [f.__dict__ for f in item.get_files(source=args['--source'])]

    output = []
    for f in files:
        file_dict = {}
        for key, val in f.items():
            if key in columns:
                if six.PY2:
                    val = val.encode('utf-8')
                if key == 'name' and args.get('--location'):
                    file_dict[key] = ('https://archive.org/download/'
                                      '{id}/{f}'.format(id=item.identifier, f=val))
                else:
                    file_dict[key] = val
        output.append(file_dict)

    if args['--verbose']:
        dict_writer.writer.writerow(columns)
    if all(x == {} for x in output):
        sys.exit(0)
    dict_writer.writerows(output)
