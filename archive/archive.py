import time
import os
import json
import math
import multiprocessing
import urllib
import httplib

import filechunkio
import requests
from boto.s3.connection import S3Connection, OrdinaryCallingFormat
import boto
import jsonpatch



# S3 Multi-Part Upload (Must be outside of class (I'm probably doing this
# wrong :)) >>>
#_________________________________________________________________________________________
def _upload_part(conn, bucketname, multipart_id, part_num, source_path, offset,
                 bytes, amount_of_retries=10):
    """
    Upload a part of a file with retries.
    """
    def _upload(retries_left=amount_of_retries):
        try:
            bucket = conn.get_bucket(bucketname)
            for mp in bucket.get_all_multipart_uploads():
                if mp.id == multipart_id:
                    with filechunkio.FileChunkIO(source_path, 'r',
                                                 offset=offset,
                                                 bytes=bytes) as fp:
                        mp.upload_part_from_file(fp=fp, part_num=part_num)
                    break
        except Exception, exc:
            if retries_left:
                _upload(retries_left=retries_left - 1)
            else:
                raise exc
        #else:
        #    print ''
            #continue

    _upload()


# Item class
#_________________________________________________________________________________________
class Item(object):
    """This class represents an archive.org item.
    You can use this class to access item metadata:
        >>> import archive
        >>> item = archive.Item('stairs')
        >>> print item.metadata

    This class also uses IA's S3-like interface to upload files to an item. You need to
    supply your IAS3 credentials in environment variables in order to upload. You can
    retrieve S3 keys from https://archive.org/account/s3.php
        >>> import os;
        >>> os.environ['AWS_ACCESS_KEY_ID']='x'; os.environ['AWS_SECRET_ACCESS_KEY']='y'
        >>> item.upload('myfile')
        True
    """

    # init()
    #_____________________________________________________________________________________
    def __init__(self, identifier):
        self.identifier = identifier
        self.details_url = 'https://archive.org/details/{0}'.format(identifier)
        self.download_url = 'http://archive.org/download/{0}'.format(identifier)
        self.metadata_url = 'http://archive.org/metadata/{0}'.format(identifier)
        self.req = requests.get(self.metadata_url)
        self._s3_conn = None
        self.metadata = self.req.json()
        if self.metadata == {}:
            self.exists = False
        else:
            self.exists = True


    # files()
    #_____________________________________________________________________________________
    def files(self):
        """Generator for iterating over files in an item"""
        for file_dict in self.metadata['files']:
            file = File(self, file_dict)
            yield file


    # file()
    #_____________________________________________________________________________________
    def file(self, name):
        """Return an archive.File object for the named file.
        If the specified file was not found in the item, return None
        """
        for file_dict in self.metadata['files']:
            if file_dict['name'] == name:
                return File(self, file_dict)
        return None


    # download()
    #_____________________________________________________________________________________
    def download(self):
        """Download the entire item into the current working directory"""
        for f in self.files():
            print '  downloading', f.name
            path = os.path.join(self.identifier, f.name)
            parent_dir = os.path.dirname(path)
            f.download(path)


    # modify_metadata()
    #_____________________________________________________________________________________
    def modify_metadata(self, metadata, target='metadata'):
        """function for modifying the metadata of an existing item on archive.org.
        Note: The Metadata Write API does not yet comply with the latest Json-Patch
        standard. It currently complies with version 02:

        https://tools.ietf.org/html/draft-ietf-appsawg-json-patch-02

        :param metadata: Dictionary. Metadata used to update the item.
        :param target: (optional) String. Metadata target to update.

        Usage:

        >>> import archive
        >>> item = archive.Item('mapi_test_item1')
        >>> md = dict(new_key='new_value', foo=['bar', 'bar2'])
        >>> item.modify_metadata(md)

        """
        access_key = os.environ['AWS_ACCESS_KEY_ID']
        secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
        src = self.metadata.get(target, {})
        dest = dict((src.items() + metadata.items()))

        # Prepare patch to remove metadata elements with the value: "REMOVE_TAG".
        for k,v in metadata.items():
            if v == 'REMOVE_TAG' or not v:
                del dest[k]

        json_patch = jsonpatch.make_patch(src, dest).patch
        # Reformat patch to be compliant with version 02 of the Json-Patch standard.
        patch = []
        for p in json_patch:
            pd = {p['op']: p['path']}
            if p['op'] != 'remove':
                pd['value'] = p['value']
            patch.append(dict((k,v) for k,v in pd.items() if v))

        data = {
            '-patch': json.dumps(patch),
            '-target': target,
            'access': access_key,
            'secret': secret_key,
        }

        host = 'archive.org'
        path = '/metadata/{0}'.format(self.identifier)
        http = httplib.HTTP(host)
        http.putrequest("POST", path)
        http.putheader("Host", host)
        data = urllib.urlencode(data)
        http.putheader("Content-Type", 'application/x-www-form-urlencoded')
        http.putheader("Content-Length", str(len(data)))
        http.endheaders()
        http.send(data)
        status_code, error_message, headers = http.getreply()
        resp_file = http.getfile()
        return dict(
            status_code = status_code,
            error_message = error_message,
            headers = headers,
            content = json.loads(resp_file.read()),
        )


    # _get_s3_conn()
    #_____________________________________________________________________________________
    def _get_s3_conn(self):
        if self._s3_conn is None:
            self._s3_conn = S3Connection(host='s3.us.archive.org', is_secure=False,
                                         calling_format=OrdinaryCallingFormat())
        return self._s3_conn


    # _get_s3_bucket()
    #_____________________________________________________________________________________
    def _get_s3_bucket(self, conn, headers={}, ignore_bucket=False):
        if ignore_bucket is True:
            bucket = None
        else:
            bucket = conn.lookup(self.identifier)
        if bucket:
            return bucket
        headers['x-archive-queue-derive'] = 0
        bucket = conn.create_bucket(self.identifier, headers=headers)
        i=0
        while i<60:
            b = conn.lookup(self.identifier)
            if b:
                return bucket
            time.sleep(10)
            i+=1
        raise NameError('Could not create or lookup %s' % self.identifier)


    # upload()
    #_____________________________________________________________________________________
    def upload(self, files, meta_dict={}, headers={}, dry_run=False,
               derive=True, multipart=False, ignore_bucket=False,
               parallel_processes=4):
        """Upload file(s) to an item. The item will be created if it does not
        exist.

        :param files: Either a list of filepaths, or a string pointing to a single file.
        :param meta_dict: Dictionary of metadata used to create a new item.
        :param dry_run: (optional) Boolean. Set to True to print headers to stdout -- don't upload anything.
        :param derive: (optional) Boolean. Set to False to prevent an item from being derived after upload.
        :param multipart: (optional) Boolean. Set to True to upload files in parts. Useful when uploading large files.
        :param ignore_bucket: (optional) Boolean. Set to True to ignore and clobber existing files and metadata.
        :param parallel_processes: (optional) Integer. Only used when :param:`multipart` is ``True``.

        Usage::

            >>> import archive
            >>> item = archive.Item('identifier')
            >>> item.upload('/path/to/image.jpg', dict(mediatype='image', creator='Jake Johnson'))
        """
        # Convert metadata from :meta_dict: into S3 headers
        for key,v in meta_dict.iteritems():
            if type(v) == list:
                i=1
                for value in v:
                    s3_header_key = 'x-archive-meta{0:02d}-{1}'.format(i, key)
                    headers[s3_header_key] = value.encode('utf-8')
                    i+=1
            else:
                s3_header_key = 'x-archive-meta-%s' % key
                if type(v) != int:
                    headers[s3_header_key] = v.encode('utf-8')
                else:
                    headers[s3_header_key] = v
        headers = {k: str(v) for k,v in headers.iteritems() if v}

        if dry_run:
            return headers

        if type(files) != list:
            files = [files]
        for file in files:
            filename = file.split('/')[-1]
            conn = self._get_s3_conn()
            bucket = self._get_s3_bucket(conn, headers, ignore_bucket=ignore_bucket)
            #headers['x-archive-ignore-preexisting-bucket'] = 1

            if bucket.get_key(filename):
                continue

            if not derive:
                headers = {'x-archive-queue-derive': 0}

            if not multipart:
                k = boto.s3.key.Key(bucket)
                k.name = filename
                k.set_contents_from_filename(file, headers=headers)
            else:
                parallel_processes=4
                mp = bucket.initiate_multipart_upload(filename, headers=headers)
                source_size = os.stat(file).st_size
                headers['x-archive-size-hint'] = source_size
                bytes_per_chunk = (max(int(math.sqrt(5242880) *
                                           math.sqrt(source_size)), 5242880))
                chunk_amount = (int(math.ceil(source_size /
                                float(bytes_per_chunk))))
                pool = multiprocessing.Pool(processes=parallel_processes)
                for i in range(chunk_amount):
                    offset = i * bytes_per_chunk
                    remaining_bytes = source_size - offset
                    bytes = min([bytes_per_chunk, remaining_bytes])
                    part_num = i + 1
                    pool.apply_async(_upload_part,
                                     [conn, self.identifier, mp.id, part_num, file,
                                      offset, bytes])
                pool.close()
                pool.join()
                if len(mp.get_all_parts()) == chunk_amount:
                    mp.complete_upload()
                    key = bucket.get_key(filename)
                else:
                    mp.cancel_upload()
        return True


# File class
#_________________________________________________________________________________________
class File(object):

    # init()
    #_____________________________________________________________________________________
    def __init__(self, item, file_dict):
        def get(d, key):
            if key in d:
                return d[key]
            else:
                return None

        self.item = item
        self.name = file_dict['name']
        self.md5  = file_dict['md5']
        self.sha1 = get(file_dict, 'sha1')
        self.size = get(file_dict, 'size')
        if self.size is not None:
            self.size = int(self.size)


    # download()
    #_____________________________________________________________________________________
    def download(self, file_path=None):
        if file_path is None:
            file_path = self.name

        if os.path.exists(file_path):
            raise IOError('File already exists: %s' % file_path)

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        url = 'https://archive.org/download/%s/%s' % (self.item.identifier, self.name)
        urllib.urlretrieve(url, file_path)


# Catalog class
#_________________________________________________________________________________________
class Catalog(object):

    # init()
    #_____________________________________________________________________________________
    def __init__(self, params=None):
        if not params:
            params = {'justme': 1}
        params['json'] = 2
        params['output'] = 'json'
        params['callback'] = 'foo'
        url = 'http://www.us.archive.org/catalog.php'
        LOG_IN_COOKIES = {
                'logged-in-sig': os.environ['LOGGED_IN_SIG'],
                'logged-in-user': os.environ['LOGGED_IN_USER'],
        }
        r = requests.get(url, params=params, cookies=LOG_IN_COOKIES)

        # This ugly little line is used to parse the faux JSON available from
        # catalog.php
        self.tasks_json = json.loads(r.text.strip('foo').strip().strip('()'))
        self.tasks = []
        for t in self.tasks_json:
            td = {}
            td['identifier'] = t[0]
            td['server'] = t[1]
            td['command'] = t[2]
            td['time'] = t[3]
            td['submitter'] = t[4]
            td['args'] = t[5]
            td['task_id'] = t[6]
            td['type'] = t[7]
            self.tasks.append(td)

        self.green_rows = [x for x in self.tasks if x['type'] == 0]
        self.blue_rows = [x for x in self.tasks if x['type'] == 1]
        self.red_rows = [x for x in self.tasks if x['type'] == 2]
        self.brown_rows = [x for x in self.tasks if x['type'] == 9]
