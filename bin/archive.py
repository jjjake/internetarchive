#!/usr/bin/env python
import argparse
import sys

import internetarchive



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
    elif upload_status is False:
        sys.stderr.write('error: upload failed!\n')
    else:
        sys.stdout.write('uploaded:\t{0}\n'.format(item.details_url))


# metadata()
#_________________________________________________________________________________________
def metadata():
    pass


# main()
#_________________________________________________________________________________________
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='archive.py')
    subparsers = parser.add_subparsers(help='sub-command help')

    # Upload parser.
    parser_upload = subparsers.add_parser('upload', help='upload help')
    parser_upload.add_argument('files', nargs='*', type=str, default=None)
    parser_upload.add_argument('--identifier', '-id', type=str, action='append')
    parser_upload.add_argument('--derive', default=True, action='store_false')
    parser_upload.add_argument('--multipart', default=False, action='store_true')
    parser_upload.add_argument('--ignore-bucket', default=False, action='store_true')
    parser_upload.add_argument('--dry-run', default=False, action='store_true')
    parser_upload.add_argument('--header', '-H', type=str, default=[], action='append')
    parser_upload.add_argument('--metadata', '-md', type=str, action='append')
    parser_upload.set_defaults(func=upload)
    
    # Metadata parser.
    # TODO: Add metadata sub-command for editing and retrieving metadata from Archive.org
    parser_metadata = subparsers.add_parser('metadata', help='upload help')
    parser_metadata.add_argument('foo', nargs='*', type=str, default=None)
    parser_metadata.set_defaults(func=metadata)

    # Args.
    args = parser.parse_args()
    args.func(args)
