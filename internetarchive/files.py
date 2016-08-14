# -*- coding: utf-8 -*-
#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2016 Internet Archive
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

:copyright: (C) 2012-2016 by Internet Archive.
:license: AGPL 3, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals, print_function

import os
import sys
import logging
import socket

import six.moves.urllib as urllib
from requests.exceptions import HTTPError, RetryError, ConnectTimeout, \
    ConnectionError, ReadTimeout

from internetarchive import iarequest, utils


log = logging.getLogger(__name__)


class BaseFile(object):

    def __init__(self, item_metadata, name):
        _file = {}
        for f in item_metadata.get('files', []):
            if f.get('name') == name:
                _file = f
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

        self.exists = True if _file else False

        for key in _file:
            setattr(self, key, _file[key])
        self.mtime = float(self.mtime) if self.mtime else 0
        self.size = int(self.size) if self.size else 0


# File class
# ________________________________________________________________________________________
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
    def __init__(self, item, name):
        """
        :type item: Item
        :param item: The item that the file is part of.

        :type name: str
        :param name: The filename of the file.

        """
        super(File, self).__init__(item.item_metadata, name)
        self.item = item
        url_parts = dict(
            protocol=item.session.protocol,
            id=self.identifier,
            name=urllib.parse.quote(name.encode('utf-8')),
        )
        self.url = '{protocol}//archive.org/download/{id}/{name}'.format(**url_parts)

    def __repr__(self):
        return ('File(identifier={identifier!r}, '
                'filename={name!r}, '
                'size={size!r}, '
                'format={format!r})'.format(**self.__dict__))

    # download()
    # ____________________________________________________________________________________
    def download(self, file_path=None, verbose=None, silent=None, ignore_existing=None,
                 checksum=None, destdir=None, retries=None, ignore_errors=None):
        """Download the file into the current working directory.

        :type file_path: str
        :param file_path: Download file to the given file_path.

        :type ignore_existing: bool
        :param ignore_existing: Overwrite local files if they already
                                exist.

        :type checksum: bool
        :param checksum: Skip downloading file based on checksum.

        """
        verbose = False if verbose is None else verbose
        silent = False if silent is None else silent
        ignore_existing = False if ignore_existing is None else ignore_existing
        checksum = False if checksum is None else checksum
        retries = 2 if not retries else retries
        ignore_errors = False if not ignore_errors else ignore_errors

        self.item.session._mount_http_adapter(max_retries=retries)
        file_path = self.name if not file_path else file_path

        if destdir:
            if not os.path.exists(destdir):
                os.mkdir(destdir)
            if os.path.isfile(destdir):
                raise IOError('{} is not a directory!'.format(destdir))
            file_path = os.path.join(destdir, file_path)

        if os.path.exists(file_path):
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
                md5_sum = utils.get_md5(open(file_path, 'rb'))
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
                st = os.stat(file_path)
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
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)

        try:
            response = self.item.session.get(self.url, stream=True, timeout=12)
            response.raise_for_status()

            chunk_size = 2048
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        f.flush()
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
        os.utime(file_path, (0, self.mtime))

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
               debug=None, retries=None):
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
        cascade_delete = False if not cascade_delete else True
        access_key = self.item.session.access_key if not access_key else access_key
        secret_key = self.item.session.secret_key if not secret_key else secret_key
        debug = False if not debug else debug
        verbose = False if not verbose else verbose
        max_retries = 2 if retries is None else retries

        url = '{0}//s3.us.archive.org/{1}/{2}'.format(self.item.session.protocol,
                                                      self.identifier,
                                                      self.name)
        self.item.session._mount_http_adapter(max_retries=max_retries,
                                              status_forcelist=[503],
                                              host='s3.us.archive.org')
        request = iarequest.S3Request(
            method='DELETE',
            url=url,
            headers={'x-archive-cascade-delete': int(cascade_delete)},
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
            prepared_request = request.prepare()

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
