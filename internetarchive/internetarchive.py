try:
    import ujson as json
except ImportError:
    import json
import urllib
import os
import httplib
import time
import math
import urllib2

import jsonpatch
from boto.s3.connection import S3Connection, OrdinaryCallingFormat
import boto
import filechunkio



# Item class
#_________________________________________________________________________________________
class Item(object):
    """This class represents an archive.org item.
    You can use this class to access item metadata:
        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
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
        self.download_url = 'https://archive.org/download/{0}'.format(identifier)
        self.metadata_url = 'https://archive.org/metadata/{0}'.format(identifier)
        self._s3_conn = None
        self.metadata = self._get_item_metadata()
        if self.metadata == {}:
            self.exists = False
        else:
            self.exists = True


    # _get_item_metadata()
    #_____________________________________________________________________________________
    def _get_item_metadata(self):
        f = urllib.urlopen(self.metadata_url)
        return json.loads(f.read())


    # files()
    #_____________________________________________________________________________________
    def files(self):
        """Generator for iterating over files in an item"""
        for file_dict in self.metadata.get('files', []):
            file = File(self, file_dict)
            yield file


    # file()
    #_____________________________________________________________________________________
    def file(self, name):
        """Return an archive.org File object for the named file.
        If the specified file was not found in the item, return None
        """
        for file_dict in self.metadata['files']:
            if file_dict['name'] == name:
                return File(self, file_dict)
        return None


    # download()
    #_____________________________________________________________________________________
    def download(self, formats=None):
        """Download the entire item into the current working directory"""
        for f in self.files():
            if type(formats) == str:
                formats = [formats]
            if formats is not None and f.format not in formats:
                continue
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

        >>> import internetarchive
        >>> item = internetarchive.Item('mapi_test_item1')
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
        self.metadata = self._get_item_metadata()
        return dict(
            status_code = status_code,
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
            headers['x-archive-ignore-preexisting-bucket'] = 1
            bucket = None
        else:
            bucket = conn.lookup(self.identifier)
        if bucket:
            return bucket
        bucket = conn.create_bucket(self.identifier, headers=headers)
        i=0
        while i<60:
            b = conn.lookup(self.identifier)
            if b:
                return bucket
            time.sleep(10)
            i+=1
        raise NameError('Could not create or lookup {0}'.format(self.identifier))


    # upload()
    #_____________________________________________________________________________________
    def upload(self, files, meta_dict={}, headers={}, dry_run=False,
               derive=True, multipart=False, ignore_bucket=False):
        """Upload file(s) to an item. The item will be created if it does not
        exist.

        :param files: Either a list of filepaths, or a string pointing to a single file.
        :param meta_dict: Dictionary of metadata used to create a new item.
        :param dry_run: (optional) Boolean. Set to True to print headers to stdout -- don't upload anything.
        :param derive: (optional) Boolean. Set to False to prevent an item from being derived after upload.
        :param multipart: (optional) Boolean. Set to True to upload files in parts. Useful when uploading large files.
        :param ignore_bucket: (optional) Boolean. Set to True to ignore and clobber existing files and metadata.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> item.upload('/path/to/image.jpg', dict(mediatype='image', creator='Jake Johnson'))
        """
        # Convert metadata from :meta_dict: into S3 headers
        for key,v in meta_dict.iteritems():
            if type(v) == list:
                for i, value in enumerate(v):
                    s3_header_key = 'x-archive-meta{0:02d}-{1}'.format(i, key)
                    if type(value) == str:
                        headers[s3_header_key] = value.encode('utf-8')
                    else:
                        headers[s3_header_key] = value
            else:
                s3_header_key = 'x-archive-meta-{0}'.format(key)
                if type(v) == str:
                    headers[s3_header_key] = v.encode('utf-8')
                else:
                    headers[s3_header_key] = v
        headers = dict((k, v) for k, v in headers.iteritems() if v)

        if dry_run:
            return headers

        if type(files) != list:
            files = [files]
        for f in files:
            if type(f) == str:
                f = file(f, 'rb')
            filename = f.name.split('/')[-1]
            conn = self._get_s3_conn()
            bucket = self._get_s3_bucket(conn, headers, ignore_bucket=ignore_bucket)

            if not derive:
                headers = {'x-archive-queue-derive': 0}

            if bucket.get_key(filename) and ignore_bucket is False:
                continue

            if not multipart:
                k = boto.s3.key.Key(bucket)
                k.name = filename
                k.set_contents_from_file(f, headers=headers)
            else:
                mp = bucket.initiate_multipart_upload(filename, headers=headers)
                source_size = os.stat(f).st_size
                headers['x-archive-size-hint'] = source_size
                bytes_per_chunk = (max(int(math.sqrt(5242880) *
                                           math.sqrt(source_size)), 5242880))
                chunk_amount = (int(math.ceil(source_size/float(bytes_per_chunk))))
                for i in range(chunk_amount):
                    offset = i * bytes_per_chunk
                    remaining_bytes = source_size - offset
                    part_bytes = min([bytes_per_chunk, remaining_bytes])
                    part_num = i + 1
                    with filechunkio.FileChunkIO(f, 'r',
                                                 offset=offset,
                                                 bytes=part_bytes) as f:
                        mp.upload_part_from_file(fp=f, part_num=part_num)
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
        self.item = item
        self.external_identifier = file_dict.get('external-identifier')
        self.name = file_dict.get('name')
        self.source = file_dict.get('source')
        self.size = file_dict.get('size')
        self.size = file_dict.get('size')
        if self.size is not None:
            self.size = int(self.size)
        self.format = file_dict.get('format') 
        self.mtime = file_dict.get('mtime')
        self.md5  = file_dict.get('md5')
        self.sha1 = file_dict.get('crc32')
        self.sha1 = file_dict.get('sha1')


    # download()
    #_____________________________________________________________________________________
    def download(self, file_path=None):
        if file_path is None:
            file_path = self.name

        if os.path.exists(file_path):
            raise IOError('File already exists: {0}'.format(file_path))

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        url = 'https://archive.org/download/{0}/{1}'.format(self.item.identifier,
                                                            self.name)
        urllib.urlretrieve(url, file_path)


# Search class
#_________________________________________________________________________________________
class Search(object):
    """This class represents an archive.org item search. You can use this class to search
    for archive.org items using the advanced search engine:
        >>> import internetarchive
        >>> search = internetarchive.Search('(uploader:jake@archive.org)')
        >>> for result in search.results: 
        ...     print result['identifier']
    """

    # init()
    #_____________________________________________________________________________________
    def __init__(self, query, fields=['identifier'], params={}):
        self._base_url = 'https://archive.org/advancedsearch.php'
        self.query = query
        self.params = dict(dict(
                q = self.query,
                output = params.get('output', 'json'),
                rows = 100,
        ).items() + params.items())
        # Updata params dict with fields.
        for k, v in enumerate(fields):
            key = 'fl[{0}]'.format(k)
            self.params[key] = v
        self.encoded_params = urllib.urlencode(self.params)
        self.url = '{0}?{1}'.format(self._base_url, self.encoded_params)
        self.search_info = self._get_search_info()
        self.num_found = self.search_info['response']['numFound']
        self.results = self._iter_results()


    # _get_search_info()
    #_____________________________________________________________________________________
    def _get_search_info(self):
        info_params = self.params.copy()
        info_params['rows'] = 0
        encoded_info_params = urllib.urlencode(info_params)
        f = urllib.urlopen(self._base_url, encoded_info_params)
        results = json.loads(f.read())
        del results['response']['docs']
        return results

        
    # _iter_results()
    #_____________________________________________________________________________________
    def _iter_results(self):
        """Generator for iterating over search results"""
        total_pages = ((self.num_found / self.params['rows']) + 2)
        for page in range(1, total_pages):
            self.params['page'] = page
            encoded_params = urllib.urlencode(self.params)
            f = urllib.urlopen(self._base_url, encoded_params)
            results = json.loads(f.read())
            for doc in results['response']['docs']:
                yield doc


# Catalog class
#_________________________________________________________________________________________
class Catalog(object):

    # init()
    #_____________________________________________________________________________________
    def __init__(self, params=None):
        url = 'http://archive.org/catalog.php'
        self.GREEN = 0
        self.BLUE = 1
        self.RED = 2
        self.BROWN = 9

        if not params:
            params = dict(justme = 1)

        # Add params required to retrieve JSONP from the IA catalog.
        params['json'] = 2
        params['output'] = 'json'
        params['callback'] = 'foo'
        params = urllib.urlencode(params)

        ia_cookies = ('logged-in-sig={LOGGED_IN_SIG}; '
                      'logged-in-user={LOGGED_IN_USER}; '
                      'verbose=1'.format(**os.environ))

        opener = urllib2.build_opener()
        opener.addheaders.append(('Cookie', ia_cookies))
        f = opener.open(url, params)

        # Convert JSONP to JSON (then parse the JSON).
        jsonp_str = f.read()
        json_str = jsonp_str[(jsonp_str.index("(") + 1):jsonp_str.rindex(")")]

        tasks_json = json.loads(json_str)
        self.tasks = [dict(
            identifier = t[0],
            server = t[1],
            command = t[2],
            time = t[3],
            submitter = t[4],
            # Parse args into dict
            args = dict(x for x in urllib2.urlparse.parse_qsl(t[5])),
            task_id = t[6],
            row_type = t[7],
        ) for t in tasks_json]

        self.green_rows = [t for t in self.tasks if t['row_type'] == self.GREEN]
        self.blue_rows = [t for t in self.tasks if t['row_type'] == self.BLUE]
        self.red_rows = [t for t in self.tasks if t['row_type'] == self.RED]
        self.brown_rows = [t for t in self.tasks if t['row_type'] == self.BROWN]
