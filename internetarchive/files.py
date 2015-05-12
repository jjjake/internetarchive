import os
import sys
import logging

from requests.exceptions import HTTPError
from requests import Request
from clint.textui import progress
import six.moves.urllib as urllib

from . import iarequest, utils


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


# File class
# ________________________________________________________________________________________
class File(BaseFile):
    """This class represents a file in an archive.org item. You
    can use this class to access the file metadata::

        >>> import internetarchive
        >>> item = internetarchive.Item('stairs')
        >>> file = internetarchive.File(item, 'stairs.avi')
        >>> print(f.format, f.size)
        (u'Cinepack', u'3786730')

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
    # init()
    # ____________________________________________________________________________________
    def __init__(self, item, name):
        """
        :type item: Item
        :param item: The item that the file is part of.

        :type name: str
        :param name: The filename of the file.

        """
        super(File, self).__init__(item.item_metadata, name)

        self.item = item
        self.url = ('{protocol}//archive.org/download/{identifier}/{name}'.format(
            protocol=item.session.protocol, identifier=self.identifier,
            name=urllib.parse.quote(name.encode('utf-8'))))

    # __repr__()
    # ____________________________________________________________________________________
    def __repr__(self):
        return ('File(identifier={identifier!r}, '
                'filename={name!r}, '
                'size={size!r}, '
                'source={source!r}, '
                'format={format!r})'.format(**self.__dict__))

    # download()
    # ____________________________________________________________________________________
    def download(self, file_path=None, clobber=None, checksum=None, destdir=None,
                 verbose=None, debug=None):
        """Download the file into the current working directory.

        :type file_path: str
        :param file_path: Download file to the given file_path.

        :type clobber: bool
        :param clobber: Overwrite local files if they already exist.

        :type checksum: bool
        :param checksum: Skip downloading file based on checksum.

        """
        checksum = False if not checksum else True
        clobber = False if not clobber else True
        verbose = False if not verbose else True
        debug = False if not debug else True

        file_path = self.name if not file_path else file_path

        if destdir:
            if not os.path.exists(destdir):
                os.mkdir(destdir)
            if os.path.isfile(destdir):
                raise IOError('{} is not a directory!'.format(destdir))
            file_path = os.path.join(destdir, file_path)

        if os.path.exists(file_path):
            if clobber:
                pass
            elif checksum:
                md5_sum = utils.get_md5(open(file_path))
                if md5_sum == self.md5:
                    log.info('not downloading file {0}, '
                             'file already exists.'.format(file_path))
                    if verbose:
                        sys.stderr.write(
                            ' skipping {0}: already exists.\n'.format(file_path))
                    return
            else:
                raise IOError('file already downloaded: {0}'.format(file_path))

        parent_dir = os.path.dirname(file_path)
        if parent_dir != '' and not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        request = Request(method='GET', url=self.url)
        if debug:
            return request
        try:
            prepared_request = request.prepare()
            response = self.item.session.send(prepared_request, stream=True)
            response.raise_for_status()
        except HTTPError as e:
            error_msg = 'error downloading {0}, {1}'.format(self.url, e)
            log.error(error_msg)
            raise
        with open(file_path, 'wb') as f:
            chunk_size = 1024
            if verbose:
                try:
                    total_length = int(response.headers.get('content-length'))
                    expected_size = (total_length/chunk_size) + 1
                    label = ' downloading {}: '.format(file_path)
                    content = progress.bar(response.iter_content(chunk_size=chunk_size),
                                           expected_size=expected_size, label=label)
                except:
                    sys.stderr.write(' downloading: {0}\n'.format(file_path))
                    content = response.iter_content(chunk_size=chunk_size)
            else:
                content = response.iter_content(chunk_size=chunk_size)
            for chunk in content:
                if chunk:
                    f.write(chunk)
                    f.flush()

        log.info('downloaded {0}/{1} to {2}'.format(self.identifier,
                                                    self.name.encode('utf-8'),
                                                    file_path))
        return response

    # delete()
    # ____________________________________________________________________________________
    def delete(self, cascade_delete=None, access_key=None, secret_key=None, verbose=None,
               debug=None):
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

        url = 'http://s3.us.archive.org/{0}/{1}'.format(self.identifier,
                                                        self.name.encode('utf-8'))
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
                msg = ' deleting: {0}'.format(self.name.encode('utf-8'))
                if cascade_delete:
                    msg += ' and all derivative files.\n'
                else:
                    msg += '\n'
                sys.stderr.write(msg)
            prepared_request = request.prepare()

            try:
                resp = self.item.http_session.send(prepared_request)
                resp.raise_for_status()
            except HTTPError as e:
                error_msg = 'Error deleting {0}, {1}'.format(resp.url, e)
                log.error(error_msg)
                raise
            finally:
                return resp
