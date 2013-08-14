#!/usr/bin/env python
import sys
import csv
import re
from collections import Counter

import internetarchive


# compile_metadata()
#_________________________________________________________________________________________
def compile_metadata(dirty_metadata):
    number_pattern = re.compile(r'[0-9]+')
    metadata = {}

    # Detect duplicate keys, and prepare dummy list assign values to
    key_count = Counter(x.split('[')[0] for x in dirty_metadata.keys())
    duplicate_keys = dict((k,v) for k,v in key_count.items() if v > 1)
    for k,v in duplicate_keys.items():
        metadata[k] = [None for x in range(v)]

    # Merge duplicate items, and clean out empty values
    for k,v in dirty_metadata.items():
        if v == '' or v is None:
            continue
        unique_key = k.split('[')[0]
        if unique_key in duplicate_keys:
            number_match = number_pattern.search(k)
            if not number_match:
                k_index = 0
            else:
                k_index = int(number_match.group())
            metadata[unique_key][k_index] = v
        else:
            metadata[k] = v

    # Filter out None sub-values
    for k,v in metadata.items():
        if type(v) == list:
            metadata[k] = [x for x in v if x is not None]

    # Filter out None values, and return clean dictionary
    return dict((k,v) for k,v in metadata.items() if v)


# iter_csv()
#_________________________________________________________________________________________
def iter_csv(csv_file, delimiter=",", quotechar='"'):
    with open(csv_file, 'rU') as f:
        csv_reader = csv.reader(f, delimiter=delimiter, quotechar=quotechar)
        for i, row in enumerate(csv_reader):
            if i == 0:
                headers = row
                if 'identifier' not in headers:
                    sys.stderr.write('ERROR! Missing "identifier" column.\n')
                    sys.exit(1)
                continue
            dirty_metadata = dict((k,v) for k,v in zip(headers, row))
            metadata = compile_metadata(dirty_metadata)
            if len(metadata.keys()) <= 1:
                continue
            else:
                yield metadata


# main()
#_________________________________________________________________________________________
if __name__ == '__main__':
    tab_file = sys.argv[-1]
    errors = []
    for md in iter_csv(tab_file):
        item = internetarchive.Item(md['identifier'])
        r = item.modify_metadata(md)
        if r['status_code'] != 200:
            message = '{0}\tERROR! {1}\n'.format(md['identifier'], r['content'])
            sys.stderr.write(message)
            errors.append(r)
        else:
            message = '{0}\thttps:{1}\n'.format(md['identifier'], r['content']['log'])
            sys.stdout.write(message)
    if errors == []:
        sys.exit(0)
    else:
        sys.exit(1)
