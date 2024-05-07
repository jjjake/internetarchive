#
# The internetarchive module is a Python/CLI interface to Archive.org.
#
# Copyright (C) 2012-2021 Internet Archive
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
import logging
import os
import socket
import sys
from contextlib import nullcontext, suppress
from email.utils import parsedate_to_datetime
from time import sleep
from urllib.parse import quote

from requests.exceptions import (
    ConnectionError,
    ConnectTimeout,
    HTTPError,
    ReadTimeout,
    RetryError,
)
from tqdm import tqdm

from internetarchive import auth, exceptions, iarequest, utils

log = logging.getLogger(__name__)


class BaseFile:

    def __init__(self, item_metadata, name, file_metadata=None):
        if file_metadata is None:
            file_metadata = {}
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

        self.exists = bool(file_metadata)

        for key in file_metadata:
            setattr(self, key, file_metadata[key])
        # An additional, more orderly way to access file metadata,
        # which avoids filtering the attributes.
        self.metadata = file_metadata
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
                              given file.
        """
        super().__init__(item.item_metadata, name, file_metadata)
        self.item = item
        url_parts = {
            'protocol': item.session.protocol,
            'id': self.identifier,
            'name': quote(name.encode('utf-8')),
            'host': item.session.host,
        }
        self.url = '{protocol}//{host}/download/{id}/{name}'.format(**url_parts)
        if self.item.session.access_key and self.item.session.secret_key:
            self.auth = auth.S3Auth(self.item.session.access_key,
                                    self.item.session.secret_key)
        else:
            self.auth = None

    def __repr__(self):
        return (f'File(identifier={self.identifier!r}, '
                f'filename={self.name!r}, '
                f'size={self.size!r}, '
                f'format={self.format!r})')

    def download(# noqa: max-complexity=38
                 self, file_path=None, verbose=None, ignore_existing=None,
                 checksum=None, destdir=None, retries=None, ignore_errors=None,
                 fileobj=None, return_responses=None, no_change_timestamp=None,
                 params=None, chunk_size=None, stdout=None, ors=None,
                 timeout=None):
        """Download the file into the current working directory.

        :type file_path: str
        :param file_path: Download file to the given file_path.

        :type verbose: bool
        :param verbose: (optional) Turn on verbose output.

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

        :type stdout: bool
        :param stdout: (optional) Print contents of file to stdout instead of downloading
                       to file.

        :type ors: bool
        :param ors: (optional) Append a newline or $ORS to the end of file.
                    This is mainly intended to be used internally with `stdout`.

        :type params: dict
        :param params: (optional) URL parameters to send with
                       download request (e.g. `cnt=0`).

        :rtype: bool
        :returns: True if file was successfully downloaded.
        """
        verbose = False if verbose is None else verbose
        ignore_existing = False if ignore_existing is None else ignore_existing
        checksum = False if checksum is None else checksum
        retries = retries or 2
        ignore_errors = ignore_errors or False
        return_responses = return_responses or False
        no_change_timestamp = no_change_timestamp or False
        params = params or None
        timeout = 12 if not timeout else timeout
        headers = {}
        retries_sleep = 3  # TODO: exponential sleep
        retrying = False  # for retry loop

        self.item.session.mount_http_adapter(max_retries=retries)
        file_path = file_path or self.name

        if destdir:
            if return_responses is not True:
                try:
                    os.mkdir(destdir)
                except FileExistsError:
                    pass
            if os.path.isfile(destdir):
                raise OSError(f'{destdir} is not a directory!')
            file_path = os.path.join(destdir, file_path)

        parent_dir = os.path.dirname(file_path)

        # Retry loop
        while True:
            try:
                if parent_dir != '' and return_responses is not True:
                    os.makedirs(parent_dir, exist_ok=True)

                if not return_responses \
                        and not ignore_existing \
                        and self.name != f'{self.identifier}_files.xml' \
                        and os.path.exists(file_path.encode('utf-8')):
                    st = os.stat(file_path.encode('utf-8'))
                    if st.st_size != self.size and not checksum:
                        headers = {"Range": f"bytes={st.st_size}-"}

                response = self.item.session.get(self.url,
                                                 stream=True,
                                                 timeout=timeout,
                                                 auth=self.auth,
                                                 params=params,
                                                 headers=headers)
                # Get timestamp from Last-Modified header
                last_mod_header = response.headers.get('Last-Modified')
                if last_mod_header:
                    dt = parsedate_to_datetime(last_mod_header)
                    last_mod_mtime = dt.timestamp()
                else:
                    last_mod_mtime = self.mtime

                response.raise_for_status()

                # Check if we should skip...
                if not return_responses and os.path.exists(file_path.encode('utf-8')):
                    if ignore_existing:
                        msg = f'skipping {file_path}, file already exists.'
                        log.info(msg)
                        if verbose:
                            print(f' {msg}', file=sys.stderr)
                        return
                    elif checksum:
                        with open(file_path, 'rb') as fp:
                            md5_sum = utils.get_md5(fp)

                        if md5_sum == self.md5:
                            msg = f'skipping {file_path}, file already exists based on checksum.'
                            log.info(msg)
                            if verbose:
                                print(f' {msg}', file=sys.stderr)
                            return
                    elif not fileobj:
                        st = os.stat(file_path.encode('utf-8'))
                        if st.st_mtime == last_mod_mtime:
                            if self.name == f'{self.identifier}_files.xml' \
                                or (st.st_size == self.size):
                                msg = (f'skipping {file_path}, file already exists based on '
                                        'length and date.')
                                log.info(msg)
                                if verbose:
                                    print(f' {msg}', file=sys.stderr)
                                return

                elif return_responses:
                    return response

                if verbose:
                    total = int(response.headers.get('content-length', 0)) or None
                    progress_bar = tqdm(desc=f' downloading {self.name}',
                                        total=total,
                                        unit='iB',
                                        unit_scale=True,
                                        unit_divisor=1024)
                else:
                    progress_bar = nullcontext()

                if not chunk_size:
                    chunk_size = 1048576
                if stdout:
                    fileobj = os.fdopen(sys.stdout.fileno(), 'wb', closefd=False)
                if not fileobj or retrying:
                    if 'Range' in headers:
                        fileobj = open(file_path.encode('utf-8'), 'rb+')
                    else:
                        fileobj = open(file_path.encode('utf-8'), 'wb')

                with fileobj, progress_bar as bar:
                    if 'Range' in headers:
                        fileobj.seek(st.st_size)
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            size = fileobj.write(chunk)
                            if bar is not None:
                                bar.update(size)
                    if ors:
                        fileobj.write(os.environ.get("ORS", "\n").encode("utf-8"))

                if 'Range' in headers:
                    with open(file_path, 'rb') as fh:
                        local_checksum = utils.get_md5(fh)
                    try:
                        assert local_checksum == self.md5
                    except AssertionError:
                        msg = (f"\"{file_path}\" corrupt, "
                               "checksums do not match. "
                               "Remote file may have been modified, "
                               "retry download.")
                        os.remove(file_path.encode('utf-8'))
                        raise exceptions.InvalidChecksumError(msg)
                break
            except (RetryError, HTTPError, ConnectTimeout, OSError, ReadTimeout,
                    exceptions.InvalidChecksumError) as exc:
                if retries > 0:
                    retrying = True
                    retries -= 1
                    msg = ('download failed, sleeping for '
                           f'{retries_sleep} seconds and retrying. '
                           f'{retries} retries left.')
                    log.warning(msg)
                    sleep(retries_sleep)
                    continue
                msg = f'error downloading file {file_path}, exception raised: {exc}'
                log.error(msg)
                try:
                    os.remove(file_path)
                except OSError:
                    pass
                if verbose:
                    print(f' {msg}', file=sys.stderr)
                if ignore_errors:
                    return False
                else:
                    raise exc

        # Set mtime with timestamp from Last-Modified header
        if not no_change_timestamp:
            # If we want to set the timestamp to that of the original archive...
            with suppress(OSError):  # Probably file-like object, e.g. sys.stdout.
                os.utime(file_path.encode('utf-8'), (0,last_mod_mtime))

        msg = f'downloaded {self.identifier}/{self.name} to {file_path}'
        log.info(msg)
        return True

    def delete(self, cascade_delete=None, access_key=None, secret_key=None, verbose=None,
               debug=None, retries=None, headers=None):
        """Delete a file from the Archive. Note: Some files -- such as
        <itemname>_meta.xml -- cannot be deleted.

        :type cascade_delete: bool
        :param cascade_delete: (optional) Delete all files associated with the specified
                               file, including upstream derivatives and the original.

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
        debug = debug or False
        verbose = verbose or False
        max_retries = retries or 2
        headers = headers or {}

        if 'x-archive-cascade-delete' not in headers:
            headers['x-archive-cascade-delete'] = cascade_delete

        url = f'{self.item.session.protocol}//s3.us.archive.org/{self.identifier}/{quote(self.name)}'
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
                msg = f' deleting: {self.name}'
                if cascade_delete:
                    msg += ' and all derivative files.'
                print(msg, file=sys.stderr)
            prepared_request = self.item.session.prepare_request(request)

            try:
                resp = self.item.session.send(prepared_request)
                resp.raise_for_status()
            except (RetryError, HTTPError, ConnectTimeout,
                    OSError, ReadTimeout) as exc:
                error_msg = f'Error deleting {url}, {exc}'
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
                url_prefix = f'{self.item.session.protocol}//s3.us.archive.org'
                del self.item.session.adapters[url_prefix]


class OnTheFlyFile(File):
    def __init__(self, item, name):
        """
        :type item: Item
        :param item: The item that the file is part of.

        :type name: str
        :param name: The filename of the file.

        """
        super().__init__(item.item_metadata, name)
