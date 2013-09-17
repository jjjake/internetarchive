import yaml
try:
    import ujson as json
except ImportError:
    import json
import urllib
import os
import sys
import httplib
import time
import urllib2
import fnmatch

import jsonpatch
from boto.s3.connection import S3Connection, OrdinaryCallingFormat
import boto
from cStringIO import StringIO

from . import __version__



# Item class
#_________________________________________________________________________________________
class Item(object):
    """This class represents an archive.org item. You can use this 
    class to access item metadata:
        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> print item.metadata

    This class also uses IA's S3-like interface to upload files to an 
    item. You need to supply your IAS3 credentials in environment 
    variables in order to upload. You can retrieve S3 keys from:
    https://archive.org/account/s3.php
        >>> import os
        >>> os.environ['AWS_ACCESS_KEY_ID']='$access_key'
        >>> os.environ['AWS_SECRET_ACCESS_KEY']='$secret_key'
        >>> item.upload('myfile.tar')
        True
    """

    # init()
    #_____________________________________________________________________________________
    def __init__(self, identifier, metadata_timeout=None, host=None, s3_keys=None,
                 config=None, config_file=None):
        self.config = config
        self.config_file = config_file
        self.s3_keys = s3_keys
        self.identifier = identifier
        if host:
            _url_prefix = 'https://{0}.'.format(host)
        else:
            _url_prefix = 'https://'
        self.details_url = '{0}archive.org/details/{1}'.format(_url_prefix, identifier)
        # TODO: https is not working with gevent
        self.download_url = '{0}archive.org/download/{1}'.format(_url_prefix, identifier)
        self.metadata_url = '{0}archive.org/metadata/{1}'.format(_url_prefix, identifier)
        self.metadata_timeout = metadata_timeout
        self._s3_conn = None
        self._bucket = None
        self.metadata = self._get_item_metadata()
        if self.metadata == {}:
            self.exists = False
        else:
            self.exists = True


    # _configure()
    #_____________________________________________________________________________________
    def _configure(self):
        if not self.s3_keys:
            config_file = os.path.join(os.environ['HOME'], '.config', 
                                       'internetarchive.yml')
            if os.path.exists(config_file):
                self.config_file = config_file
            else:
                config_file = os.path.join(os.environ['HOME'], '.internetarchive.yml')
                self.config_file = config_file
            if self.config_file:
                self.config = yaml.load(open(self.config_file))
                if self.config:
                    self.s3_keys = self.config.get('s3') 
            if not self.s3_keys:
                self.s3_keys = dict(
                        access_key = os.environ['AWS_ACCESS_KEY_ID'],
                        secret_key = os.environ['AWS_SECRET_ACCESS_KEY'],
                )


    # _get_item_metadata()
    #_____________________________________________________________________________________
    def _get_item_metadata(self):
        f = urllib2.urlopen(self.metadata_url, timeout=self.metadata_timeout)
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
    def download(self, source=None, formats=None, concurrent=False, glob_pattern=None, 
                 ignore_existing=False):
        """Download the entire item into the current working directory"""
        if concurrent:
            try:
                from gevent import monkey
                monkey.patch_socket()
                from gevent.pool import Pool
                pool = Pool()
            except ImportError:
                raise ImportError(
                """No module named gevent

                Downloading files concurrently requires the gevent neworking library.
                gevent and all of it's dependencies can be installed with pip:
                
                \tpip install cython git+git://github.com/surfly/gevent.git@1.0rc2#egg=gevent

                """)

        files = self.files()
        if source:
            if type(source) == str:
                source = [source]
            files = [f for f in files if f.source in source]
        if formats:
            if type(formats) == str:
                formats = [formats]
            files = [f for f in files if f.format in formats]
        if glob_pattern:
            files = [f for f in files if fnmatch.fnmatch(f.name, glob_pattern)]

        for f in files:
            fname = f.name.encode('utf-8')
            path = os.path.join(self.identifier, fname)
            sys.stdout.write('downloading: {0}\n'.format(fname))
            if concurrent:
                pool.spawn(f.download, path, ignore_existing=ignore_existing)
            else:
                f.download(path, ignore_existing=ignore_existing)
        if concurrent:
            pool.join()


    # modify_metadata()
    #_____________________________________________________________________________________
    def modify_metadata(self, metadata, target='metadata'):
        """function for modifying the metadata of an existing item on 
        archive.org.

        Note: The Metadata Write API does not yet comply with the 
        latest Json-Patch standard. It currently complies with version 
        02:

        https://tools.ietf.org/html/draft-ietf-appsawg-json-patch-02

        :type metadata: dict
        :param metadata: Metadata used to update the item.

        :type target: str
        :param target: (optional) Set the metadata target to update.

        Usage:

        >>> import internetarchive
        >>> item = internetarchive.Item('mapi_test_item1')
        >>> md = dict(new_key='new_value', foo=['bar', 'bar2'])
        >>> item.modify_metadata(md)

        """
        if not self.s3_keys:
            self._configure()
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
            'access': self.s3_keys['access_key'],
            'secret': self.s3_keys['secret_key'],
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
            if not self.s3_keys:
                self._configure()
            self._s3_conn = S3Connection(self.s3_keys['access_key'], 
                                         self.s3_keys['secret_key'],
                                         host='s3.us.archive.org', 
                                         calling_format=OrdinaryCallingFormat())
        return self._s3_conn


    # _get_s3_bucket()
    #_____________________________________________________________________________________
    def _get_s3_bucket(self, conn, headers={}, ignore_bucket=False):
        if ignore_bucket:
            headers['x-archive-ignore-preexisting-bucket'] = 1
            self._bucket = None
        else:
            if self._bucket is None:
                self._bucket = conn.lookup(self.identifier)
        if self._bucket:
            return self._bucket
        self._bucket = conn.create_bucket(self.identifier, headers=headers)
        i=0
        while i<60:
            b = conn.lookup(self.identifier)
            if b:
                return self._bucket
            time.sleep(10)
            i+=1
        raise NameError('Could not create or lookup {0}'.format(self.identifier))


    # _get_s3_headers()
    #_____________________________________________________________________________________
    def _get_s3_headers(self, headers, metadata):
        """Convert metadata from :metadata: into S3 headers"""
        for key,v in metadata.iteritems():
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
        return dict((k, v) for k, v in headers.iteritems() if v)


    # upload_file()
    #_____________________________________________________________________________________
    def upload_file(self, _file, remote_name=None, metadata={}, headers={}, derive=True,
                    ignore_bucket=False, multipart=False, bytes_per_chunk=16777216,
                    debug=False):
        """Upload a single file to an item. The item will be created 
        if it does not exist.

        :type _file: str or file
        :param _file: The filepath or file-like object to be uploaded.

        :type remote_name: str
        :param remote_name: (optional) Sets the remote filename.

        :type metadata: dict
        :param metadata: (optional) Metadata used to create a new item.

        :type headers: dict
        :param headers: (optional) Add additional IA-S3 headers to 
                        request.

        :type derive: bool
        :param derive: (optional) Set to False to prevent an item from 
                       being derived after upload.

        :type multipart: bool
        :param multipart: (optional) Set to True to upload files in 
                          parts. Useful when uploading large files.

        :type ignore_bucket: bool
        :param ignore_bucket: (optional) Set to True to ignore and 
                              clobber existing files and metadata.

        :type debug: bool
        :param debug: (optional) Set to True to print headers to stdout,
                      and exit without sending the upload request.

        :type bytes_per_chunk: int
        :param bytes_per_chunk: (optional) Used to determine the chunk 
                                size when using multipart upload.

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> item.upload_file('/path/to/image.jpg', 
            ...                  remote_name='photos/image1.jpg')
            True
        """

        headers = self._get_s3_headers(headers, metadata)
        header_names = [header_name.lower() for header_name in headers.keys()]
        if 'x-archive-size-hint' not in header_names:
            headers['x-archive-size-hint'] = os.stat(_file).st_size
        scanner = 'Internet Archive Python library {0}'.format(__version__)
        headers['x-archive-meta-scanner'] = scanner

        if type(_file) == str:
            _file = file(_file, 'rb')
        if remote_name is None:
            remote_name = _file.name.split('/')[-1]

        conn = self._get_s3_conn()
        bucket = self._get_s3_bucket(conn, headers, ignore_bucket=ignore_bucket)

        if not derive:
            headers['x-archive-queue-derive'] =  0

        # Don't clobber existing files unless ignore_bucket is True.
        if bucket.get_key(remote_name) and not ignore_bucket:
            return True

        if not multipart:
            k = boto.s3.key.Key(bucket)
            k.name = remote_name
            k.set_contents_from_file(_file, headers=headers)
        else:
            mp = bucket.initiate_multipart_upload(remote_name, headers=headers)
            def read_chunk():
                return _file.read(bytes_per_chunk)
            part = 1
            for chunk in iter(read_chunk, ''):
                part_fp = StringIO(chunk)
                mp.upload_part_from_file(part_fp, part_num=part)
                part += 1
            mp.complete_upload()
        return True


    # upload()
    #_____________________________________________________________________________________
    def upload(self, files, **kwargs):
        """Upload files to an item. The item will be created if it 
        does not exist.

        :type files: list
        :param files: The filepaths or file-like objects to upload.

        :type kwargs: dict
        :param kwargs: The keyword arguments from the call to 
                       upload_file().

        Usage::

            >>> import internetarchive
            >>> item = internetarchive.Item('identifier')
            >>> md = dict(mediatype='image', creator='Jake Johnson')
            >>> item.upload('/path/to/image.jpg', md, derive=False)
            True
        """

        if kwargs.get('debug'):
            return self._get_s3_headers(kwargs.get('headers', {}), 
                                        kwargs.get('metadata', {}))
        if type(files) != list:
            files = [files]
        for _file in files:
            upload_status = self.upload_file(_file, **kwargs)
            if upload_status:
                continue
            else:
                return False
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
    def download(self, file_path=None, ignore_existing=False):
        if file_path is None:
            file_path = self.name

        if os.path.exists(file_path) and not ignore_existing:
            raise IOError('File already exists: {0}'.format(file_path))

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        fname = self.name.encode('utf-8')
        url = '{0}/{1}'.format(self.item.download_url, fname)
        urllib.urlretrieve(url, file_path)


# Search class
#_________________________________________________________________________________________
class Search(object):
    """This class represents an archive.org item search. You can use 
    this class to search for archive.org items using the advanced 
    search engine.

    Usage::

        >>> import internetarchive
        >>> search = internetarchive.Search('(uploader:jake@archive.org)')
        >>> for result in search.results:
        ...     print result['identifier']
    """

    # init()
    #_____________________________________________________________________________________
    def __init__(self, query, fields=['identifier'], params={}):
        self._base_url = 'http://archive.org/advancedsearch.php'
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


# Mine class
#_________________________________________________________________________________________
class Mine(object):
    """
    Usage::
        >>> miner = internetarchive.Mine('itemlist.txt', workers=50)
        >>> for md in miner:
        ...     print md
    """
    # __init__()
    #_____________________________________________________________________________________
    def __init__(self, identifiers, workers=20):
        try:
            from gevent import monkey, queue
            monkey.patch_all()
        except ImportError:
            raise ImportError(
            """No module named gevent

            This feature requires the gevent neworking library.  gevent 
            and all of it's dependencies can be installed with pip:
            
            \tpip install cython git+git://github.com/surfly/gevent.git@1.0rc2#egg=gevent

            """)

        self.hosts = None
        self.skips = []
        self.queue = queue
        self.workers = workers
        self.done_queueing_input = False
        self.queued_count = 0
        self.identifiers = identifiers
        self.input_queue = self.queue.JoinableQueue(1000)
        self.json_queue = self.queue.Queue(1000)


    # _metadata_getter()
    #_____________________________________________________________________________________
    def _metadata_getter(self):
        import random
        while True:
            i, identifier = self.input_queue.get()
            if self.hosts:
                host = self.hosts[random.randrange(len(self.hosts))]
                while host in self.skips:
                    host = hosts[random.randrange(len(self.hosts))]
            else:
                host = None
            try:
                item = Item(identifier, host=host)
                self.json_queue.put((i, item))
            except:
                if host:
                    sys.stderr.write('host failed: {0}\n'.format(host))
                    self.skips.append(host)
                self.input_queue.put((i, identifier))
            finally:
                self.input_queue.task_done()


    # _queue_input()
    #_____________________________________________________________________________________
    def _queue_input(self):
        for i, identifier in enumerate(self.identifiers):
            self.input_queue.put((i, identifier))
            self.queued_count += 1
        self.done_queueing_input = True


    # items()
    #_____________________________________________________________________________________
    def items(self):
        import gevent
        gevent.spawn(self._queue_input)
        for i in range(self.workers):
            gevent.spawn(self._metadata_getter)

        def metadata_iterator_helper():
            got_count = 0
            while True:
                if self.done_queueing_input and got_count == self.queued_count:
                    break
                yield self.json_queue.get()
                got_count += 1

        return metadata_iterator_helper()



#_________________________________________________________________________________________
class Catalog(object):
    GREEN = 0
    BLUE = 1
    RED = 2
    BROWN = 9

    # init()
    #_____________________________________________________________________________________
    def __init__(self, params=None, cookies=None):
        self.cookies = cookies
        if not self.cookies:
            self.config = self._configure()
        url = 'http://archive.org/catalog.php'

        if params is None:
            params = dict(justme = 1)

        # Add params required to retrieve JSONP from the IA catalog.
        params['json'] = 2
        params['output'] = 'json'
        params['callback'] = 'foo'
        params = urllib.urlencode(params)

        ia_cookies = ('logged-in-sig={logged-in-sig}; '
                      'logged-in-user={logged-in-user}; '
                      'verbose=1'.format(**self.cookies))

        opener = urllib2.build_opener()
        opener.addheaders.append(('Cookie', ia_cookies))
        f = opener.open(url, params)

        # Convert JSONP to JSON (then parse the JSON).
        jsonp_str = f.read()
        json_str = jsonp_str[(jsonp_str.index("(") + 1):jsonp_str.rindex(")")]

        tasks_json = json.loads(json_str)
        self.tasks = [CatalogTask(t) for t in tasks_json]
        

    # _configure()
    #_____________________________________________________________________________________
    def _configure(self):
        config_file = os.path.join(os.environ['HOME'], '.config', 
                                   'internetarchive.yml')
        if os.path.exists(config_file):
            self.config_file = config_file
        else:
            config_file = os.path.join(os.environ['HOME'], '.internetarchive.yml')
            self.config_file = config_file
        if self.config_file:
            self.config = yaml.load(open(self.config_file))
            if self.config:
                self.cookies = self.config.get('cookies') 
        if not self.cookies:
            self.cookies = {
                    'logged-in-user': os.environ['LOGGED_IN_USER'],
                    'logged-in-sig': os.environ['LOGGED_IN_sig'],
            }


    # filter_tasks()
    #_____________________________________________________________________________________
    def filter_tasks(self, pred):
        return [t for t in self.tasks if pred(t)]


    # tasks_by_type()
    #_____________________________________________________________________________________
    def tasks_by_type(self, row_type):
        return self.filter_tasks(lambda t: t.row_type == row_type)

    # green_rows()
    #_____________________________________________________________________________________
    @property
    def green_rows(self):
        return self.tasks_by_type(self.GREEN)


    # blue_rows()
    #_____________________________________________________________________________________
    @property
    def blue_rows(self):
        return self.tasks_by_type(self.BLUE)


    # red_rows()
    #_____________________________________________________________________________________
    @property
    def red_rows(self):
        return self.tasks_by_type(self.RED)


    # brown_rows()
    #_____________________________________________________________________________________
    @property
    def brown_rows(self):
        return self.tasks_by_type(self.BROWN)


# CatalogTask class
#_________________________________________________________________________________________
class CatalogTask(object):
    """represents catalog task.
    """
    COLUMNS = ('identifier', 'server', 'command', 'time', 'submitter',
               'args', 'task_id', 'row_type')

    def __init__(self, columns):
        """:param columns: array of values, typically returned by catalog
        web service. see COLUMNS for the column name.
        """
        for a, v in map(None, self.COLUMNS, columns):
            if a: setattr(self, a, v)
        # special handling for 'args' - parse it into a dict if it is a string
        if isinstance(self.args, basestring):
            self.args = dict(x for x in urllib2.urlparse.parse_qsl(self.args))

    def __repr__(self):
        return ('CatalogTask(identifier={identifier},'
                ' task_id={task_id!r}, server={server!r},'
                ' command={command!r},'
                ' submitter={submitter!r},'
                ' row_type={row_type})'.format(**self.__dict__))

    def __getitem__(self, k):
        """dict-like access privided as backward compatibility."""
        if k in self.COLUMNS:
            return getattr(self, k, None)
        else:
            raise KeyError, k

    def open_task_log(self):
        """return file-like reading task log."""
        if self.task_id is None:
            raise ValueError, 'task_id is None'
        url = 'http://catalogd.archive.org/log/{0}'.format(self.task_id)
        return urllib2.urlopen(url)
