# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2019 Internet Archive
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
internetarchive.files
~~~~~~~~~~~~~~~~~~~~~

:copyright: (C) 2012-2019 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals, print_function

import os
import sys
import logging
import socket

import six.moves.urllib as urllib
import six
from requests.exceptions import HTTPError, RetryError, ConnectTimeout, \
    ConnectionError, ReadTimeout

from internetarchive import iarequest, utils, auth


log = logging.getLogger(__name__)


class BaseFile(object):

    def __init__(self, item_metadata, name, file_metadata=None):
        if file_metadata is None:
            file_metadata = dict()
        name = name.strip('/')
        if not file_metadata:
            for f in item_metadata.get('files', []):
                if f.get('name') == name:
                    file_metadata = f
                    break

        self.identifier = item_metadata.get('metadata', {}).get('identifier')
        self.name = name
        self.size = None
        self.source = None
        self.format = None
        self.md5 = None
        self.sha1 = None
        self.mtime = None
        self.crc32 = None

        self.exists = True if file_metadata else False

        for key in file_metadata:
            setattr(self, key, file_metadata[key])
        self.mtime = float(self.mtime) if self.mtime else 0
        self.size = int(self.size) if self.size else 0


class File(BaseFile):
    """This class represents a file in an archive.org item. You
    can use this class to access the file metadata::

        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> file = internetarchive.File(item, 'stairs.avi')
        >>> print(f.format, f.size)
        ('Cinepack', '3786730')

    Or to download a file::

        >>> file.download()
        >>> file.download('fabulous_movie_of_stairs.avi')

    This class also uses IA's S3-like interface to delete a file
    from an item. You need to supply your IAS3 credentials in
    environment variables in order to delete::

        >>> file.delete(access_key='Y6oUrAcCEs4sK8ey',
        ...             secret_key='youRSECRETKEYzZzZ')

    You can retrieve S3 keys here: `https://archive.org/account/s3.php
    <https://archive.org/account/s3.php>`__

    """
    def __init__(self, item, name, file_metadata=None):
        """
        :type item: Item
        :param item: The item that the file is part of.

        :type name: str
        :param name: The filename of the file.

        :type file_metadata: dict
        :param file_metadata: (optional) a dict of metadata for the
                              given fille.
        """
        if six.PY2:
            try:
                name = name.decode('utf-8')
            except UnicodeEncodeError:
                pass
        super(File, self).__init__(item.item_metadata, name, file_metadata)
        self.item = item
        url_parts = dict(
            protocol=item.session.protocol,
            id=self.identifier,
            name=urllib.parse.quote(name.encode('utf-8')),
            host=item.session.host,
        )
        self.url = '{protocol}//{host}/download/{id}/{name}'.format(**url_parts)
        if self.item.session.access_key and self.item.session.secret_key:
            self.auth = auth.S3Auth(self.item.session.access_key,
                                    self.item.session.secret_key)
        else:
            self.auth = None

    def __repr__(self):
        return ('File(identifier={identifier!r}, '
                'filename={name!r}, '
                'size={size!r}, '
                'format={format!r})'.format(**self.__dict__))

    def download(self, file_path=None, verbose=None, silent=None, ignore_existing=None,
                 checksum=None, destdir=None, retries=None, ignore_errors=None,
                 fileobj=None, return_responses=None, no_change_timestamp=None,
                 params=None, chunk_size=None):
        """Download the file into the current working directory.

        :type file_path: str
        :param file_path: Download file to the given file_path.

        :type verbose: bool
        :param verbose: (optional) Turn on verbose output.

        :type silent: bool
        :param silent: (optional) Suppress all output.

        :type ignore_existing: bool
        :param ignore_existing: Overwrite local files if they already
                                exist.

        :type checksum: bool
        :param checksum: (optional) Skip downloading file based on checksum.

        :type destdir: str
        :param destdir: (optional) The directory to download files to.

        :type retries: int
        :param retries: (optional) The number of times to retry on failed
                        requests.

        :type ignore_errors: bool
        :param ignore_errors: (optional) Don't fail if a single file fails to
                              download, continue to download other files.

        :type fileobj: file-like object
        :param fileobj: (optional) Write data to the given file-like object
                         (e.g. sys.stdout).

        :type return_responses: bool
        :param return_responses: (optional) Rather than downloading files to disk, return
                                 a list of response objects.

        :type no_change_timestamp: bool
        :param no_change_timestamp: (optional) If True, leave the time stamp as the
                                    current time instead of changing it to that given in
                                    the original archive.

        :type params: dict
        :param params: (optional) URL parameters to send with
                       download request (e.g. `cnt=0`).

        :rtype: bool
        :returns: True if file was successfully downloaded.
        """
        verbose = False if verbose is None else verbose
        ignore_existing = False if ignore_existing is None else ignore_existing
        checksum = False if checksum is None else checksum
        retries = 2 if not retries else retries
        ignore_errors = False if not ignore_errors else ignore_errors
        return_responses = False if not return_responses else return_responses
        no_change_timestamp = False if not no_change_timestamp else no_change_timestamp
        params = None if not params else params

        if (fileobj and silent is None) or silent is not False:
            silent = True
        else:
            silent = False

        self.item.session.mount_http_adapter(max_retries=retries)
        file_path = self.name if not file_path else file_path

        if destdir:
            if not os.path.exists(destdir) and return_responses is not True:
                os.mkdir(destdir)
            if os.path.isfile(destdir):
                raise IOError('{} is not a directory!'.format(destdir))
            file_path = os.path.join(destdir, file_path)

        if not return_responses and os.path.exists(file_path.encode('utf-8')):
            if ignore_existing:
                msg = 'skipping {0}, file already exists.'.format(file_path)
                log.info(msg)
                if verbose:
                    print(' ' + msg)
                elif silent is False:
                    print('.', end='')
                    sys.stdout.flush()
                return
            elif checksum:
                with open(file_path, 'rb') as fp:
                    md5_sum = utils.get_md5(fp)

                if md5_sum == self.md5:
                    msg = ('skipping {0}, '
                           'file already exists based on checksum.'.format(file_path))
                    log.info(msg)
                    if verbose:
                        print(' ' + msg)
                    elif silent is False:
                        print('.', end='')
                        sys.stdout.flush()
                    return
            else:
                st = os.stat(file_path.encode('utf-8'))
                if (st.st_mtime == self.mtime) and (st.st_size == self.size) \
                        or self.name.endswith('_files.xml') and st.st_size != 0:
                    msg = ('skipping {0}, file already exists '
                           'based on length and date.'.format(file_path))
                    log.info(msg)
                    if verbose:
                        print(' ' + msg)
                    elif silent is False:
                        print('.', end='')
                        sys.stdout.flush()
                    return

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' \
                and not os.path.exists(parent_dir) \
                and return_responses is not True:
            os.makedirs(parent_dir)

        try:
            response = self.item.session.get(self.url,
                                             stream=True,
                                             timeout=12,
                                             auth=self.auth,
                                             params=params)
            response.raise_for_status()
            if return_responses:
                return response

            if not chunk_size:
                chunk_size = 1000000
            if not fileobj:
                fileobj = open(file_path.encode('utf-8'), 'wb')

            with fileobj:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        fileobj.write(chunk)
        except (RetryError, HTTPError, ConnectTimeout,
                ConnectionError, socket.error, ReadTimeout) as exc:
            msg = ('error downloading file {0}, '
                   'exception raised: {1}'.format(file_path, exc))
            log.error(msg)
            if os.path.exists(file_path):
                os.remove(file_path)
            if verbose:
                print(' ' + msg)
            elif silent is False:
                print('e', end='')
                sys.stdout.flush()
            if ignore_errors is True:
                return False
            else:
                raise exc

        # Set mtime with mtime from files.xml.
        if not no_change_timestamp:
            # If we want to set the timestamp to that of the original archive...
            try:
                os.utime(file_path.encode('utf-8'), (0, self.mtime))
            except OSError:
                # Probably file-like object, e.g. sys.stdout.
                pass

        msg = 'downloaded {0}/{1} to {2}'.format(self.identifier,
                                                 self.name,
                                                 file_path)
        log.info(msg)
        if verbose:
            print(' ' + msg)
        elif silent is False:
            print('d', end='')
            sys.stdout.flush()
        return True

    def delete(self, cascade_delete=None, access_key=None, secret_key=None, verbose=None,
               debug=None, retries=None, headers=None):
        """Delete a file from the Archive. Note: Some files -- such as
        <itemname>_meta.xml -- cannot be deleted.

        :type cascade_delete: bool
        :param cascade_delete: (optional) Also deletes files derived from the file, and
                               files the file was derived from.

        :type access_key: str
        :param access_key: (optional) IA-S3 access_key to use when making the given
                           request.

        :type secret_key: str
        :param secret_key: (optional) IA-S3 secret_key to use when making the given
                           request.

        :type verbose: bool
        :param verbose: (optional) Print actions to stdout.

        :type debug: bool
        :param debug: (optional) Set to True to print headers to stdout and exit exit
                      without sending the delete request.

        """
        cascade_delete = '0' if not cascade_delete else '1'
        access_key = self.item.session.access_key if not access_key else access_key
        secret_key = self.item.session.secret_key if not secret_key else secret_key
        debug = False if not debug else debug
        verbose = False if not verbose else verbose
        max_retries = 2 if retries is None else retries
        headers = dict() if headers is None else headers

        if 'x-archive-cascade-delete' not in headers:
            headers['x-archive-cascade-delete'] = cascade_delete

        url = '{0}//s3.us.archive.org/{1}/{2}'.format(self.item.session.protocol,
                                                      self.identifier,
                                                      urllib.parse.quote(self.name))
        self.item.session.mount_http_adapter(max_retries=max_retries,
                                             status_forcelist=[503],
                                             host='s3.us.archive.org')
        request = iarequest.S3Request(
            method='DELETE',
            url=url,
            headers=headers,
            access_key=access_key,
            secret_key=secret_key
        )
        if debug:
            return request
        else:
            if verbose:
                msg = ' deleting: {0}'.format(self.name)
                if cascade_delete:
                    msg += ' and all derivative files.'
                print(msg, file=sys.stderr)
            prepared_request = self.item.session.prepare_request(request)

            try:
                resp = self.item.session.send(prepared_request)
                resp.raise_for_status()
            except (RetryError, HTTPError, ConnectTimeout,
                    ConnectionError, socket.error, ReadTimeout) as exc:
                error_msg = 'Error deleting {0}, {1}'.format(url, exc)
                log.error(error_msg)
                raise
            else:
                return resp
            finally:
                # The retry adapter is mounted to the session object.
                # Make sure to remove it after delete, so it isn't
                # mounted if and when the session object is used for an
                # upload. This is important because we use custom retry
                # handling for IA-S3 uploads.
                url_prefix = '{0}//s3.us.archive.org'.format(self.item.session.protocol)
                del self.item.session.adapters[url_prefix]


class OnTheFlyFile(File):
    def __init__(self, item, name):
        """
        :type item: Item
        :param item: The item that the file is part of.

        :type name: str
        :param name: The filename of the file.

        """
        super(OnTheFlyFile, self).__init__(item.item_metadata, name)
