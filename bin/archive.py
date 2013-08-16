#!/usr/bin/env python
import argparse
import sys

import internetarchive



# metadata()
#_________________________________________________________________________________________
def metadata(args):
    if not args.identifier:
        sys.stderr.write('error: no identifier!\n')
        sys.exit(1)
    item = internetarchive.Item(args.identifier)

    # Modify metadata.
    if args.modify:
        metadata = {}
        changes = [x.split('=') for x in args.modify]
        for k,v in changes:
            if not metadata.get(k):
                metadata[k] = v
            else:
                if type(metadata[k]) != list:
                    metadata[k] = [metadata[k]]
                metadata[k].append(v)
        response = item.modify_metadata(metadata)
        status_code = response['status_code']
        if not response['content']['success']:
            error_msg = response['content']['error']
            sys.stderr.write('error: {0} ({1})\n'.format(error_msg, status_code))
            sys.exit(1)
        tasklog = 'https:{0}'.format(response['content']['log'])
        sys.stdout.write('success: https:{0}\n'.format(response['content']['log']))

    # Get metadata.
    elif args.files_count:
        sys.stdout.write(str(item.metadata.get('files_count')))
    elif args.server:
        sys.stdout.write(str(item.metadata.get('server')))
    elif args.dir:
        sys.stdout.write(str(item.metadata.get('dir')))
    elif args.d1:
        sys.stdout.write(str(item.metadata.get('d1')))
    elif args.d2:
        sys.stdout.write(str(item.metadata.get('d2')))
    elif args.files:
        for f in item.files():
            files_md = [f.item.identifier, f.name, f.format, f.size, f.md5]
            sys.stdout.write('\t'.join([str(x) for x in files_md]) + '\n')
    elif args.item_size:
        sys.stdout.write(str(item.metadata.get('item_size')))
    else:
        sys.stdout.write(str(item.metadata))
    sys.exit(0)


# upload()
#_________________________________________________________________________________________
def upload(args):
    if not args.identifier:
        sys.stderr.write('error: no identifier!\n')
        sys.exit(1)
    if not args.files:
        sys.stderr.write('error: no files!\n')
        sys.exit(1)
    headers = dict((h.split(':') for h in args.header))
    metadata = dict((md.split('=') for md in args.metadata))
    item = internetarchive.Item(args.identifier[0])
    upload_status = item.upload(args.files, meta_dict=metadata, headers=headers,
                                dry_run=args.dry_run, derive=args.derive, 
                                multipart=args.multipart,
                                ignore_bucket=args.ignore_bucket)
    if args.dry_run:
        sys.stdout.write('IA-S3 Headers:\n\n{0}\n'.format(upload_status))
        sys.exit(0)
    elif upload_status is False:
        sys.stderr.write('error: upload failed!\n')
        sys.exit(1)
    else:
        sys.stdout.write('uploaded:\t{0}\n'.format(item.details_url))
        sys.exit(0)


# search()
#_________________________________________________________________________________________
def search(args):
    if not args.query:
        sys.stderr.write('error: no query!\n')
        sys.exit(1)
    query = ' '.join(args.query)
    search = internetarchive.Search(query)
    for result in search.results:
        sys.stdout.write(result['identifier'] + '\n')
    sys.exit(0)


# main()
#_________________________________________________________________________________________
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='archive.py')
    subparsers = parser.add_subparsers(help='sub-command help')

    # Metadata parser.
    parser_metadata = subparsers.add_parser('metadata', help='metadata help')
    parser_metadata.add_argument('identifier', nargs='?', type=str)
    parser_metadata.add_argument('--files_count', '-fc', default=False,
                                 action='store_true')
    parser_metadata.add_argument('--files', default=False, action='store_true')
    parser_metadata.add_argument('--server', default=False, action='store_true')
    parser_metadata.add_argument('--dir', default=False, action='store_true')
    parser_metadata.add_argument('--d1', default=False, action='store_true')
    parser_metadata.add_argument('--d2', default=False, action='store_true')
    parser_metadata.add_argument('--item_size', default=False, action='store_true')
    parser_metadata.add_argument('--modify', nargs='*', type=str)
    parser_metadata.set_defaults(func=metadata)

    # Upload parser.
    parser_upload = subparsers.add_parser('upload', help='upload help')
    parser_upload.add_argument('files', nargs='*', type=str, default=None)
    parser_upload.add_argument('--derive', default=True, action='store_false')
    parser_upload.add_argument('--multipart', default=False, action='store_true')
    parser_upload.add_argument('--ignore-bucket', default=False, action='store_true')
    parser_upload.add_argument('--dry-run', default=False, action='store_true')
    parser_upload.add_argument('--header', '-H', type=str, default=[], action='append')
    parser_upload.add_argument('--metadata', '-md', type=str, action='append')
    parser_upload.set_defaults(func=upload)
    
    # Search parser.
    parser_search = subparsers.add_parser('search', help='search help')
    parser_search.add_argument('query', nargs='*', type=str)
    parser_search.set_defaults(func=search)

    args = parser.parse_args()
    args.func(args)
