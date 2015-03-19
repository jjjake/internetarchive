"""
internetarchive.api
~~~~~~~~~~~~~~~~~~~

This module implements the Internetarchive API.

:copyright: (c) 2015 Internet Archive.
:license: AGPL 3, see LICENSE for more details.

"""

from . import item, search, catalog


# get_item()
# ________________________________________________________________________________________
def get_item(identifier, metadata_timeout=None, config=None, max_retries=None,
             archive_session=None):
    """Get an :class:`Item` object.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :type metadata_timeout: int
    :param metadata_timeout: (optional) Set a timeout for retrieving an item's metadata.

    :type config: dict
    :param secure: (optional) Configuration options for session.

    :type max_retries: int
    :param max_retries: (optional) Maximum number of times to request a website if the
                        connection drops.

    :type archive_session: :class:`ArchiveSession`
    :param archive_session: An :class:`ArchiveSession` object can be
                            provided via the `archive_session` parameter.

    """
    _item = item.Item(identifier, metadata_timeout=metadata_timeout, config=config,
                      max_retries=max_retries, archive_session=archive_session)
    return _item


# get_files()
# ________________________________________________________________________________________
def get_files(identifier, files=None, source=None, formats=None, glob_pattern=None,
              **kwargs):
    """Get :class:`File` objects from an item.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: (optional) Only return files matching the given filenames.

    :param source: (optional) Only return files matching the given sources.

    :param formats: (optional) Only return files matching the given formats.

    :type glob_pattern: str
    :param glob_pattern: (optional) Only return files matching the given glob pattern.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    """
    item = get_item(identifier, **kwargs)
    return item.get_files(files, source, formats, glob_pattern)


# iter_files()
# ________________________________________________________________________________________
def iter_files(identifier, **kwargs):
    """Generator for iterating over all files in an item.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    """
    _item = get_item(identifier, **kwargs)
    return _item.iter_files()


# modify_metadata()
# ________________________________________________________________________________________
def modify_metadata(identifier, metadata, target='metadata', append=False, priority=None,
                    access_key=None, secret_key=None, debug=False, **kwargs):
    """Modify the metadata of an existing item on Archive.org.


    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :type metadata: dict
    :param metadata: Metadata used to update the item.

    :type target: str
    :param target: (optional) The metadata target to update.

    :type append: bool
    :param append: (optional) set to True to append metadata values to current values
                   rather than replacing.

    :type priority: int
    :param priority: (optional) Set task priority.

    :type access_key: str
    :param access_key: (optional) IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: (optional) IA-S3 secret_key to use when making the given request.

    :type debug: bool
    :param debug: (optional) set to True to return a :class:`requests.Request <Request>`
                  object instead of sending request.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    :returns: :class:`requests.Response` object or :class:`requests.Request` object if
              debug is ``True``.

    """
    item = get_item(identifier, **kwargs)
    return item.modify_metadata(metadata, target, append, priority, access_key,
                                secret_key, debug)


# upload()
# ________________________________________________________________________________________
def upload(identifier, files, metadata=None, headers=None, access_key=None,
           secret_key=None, queue_derive=None, verbose=None, verify=None, checksum=None,
           delete=None, retries=None, retries_sleep=None, debug=None, **kwargs):
    """Upload files to an item. The item will be created if it does not exist.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :type metadata: dict
    :param metadata: (optional) Metadata used to create a new item. If the item already
                     exists, the metadata will not be updated -- use ``modify_metadata``.

    :type headers: dict
    :param headers: (optional) Add additional HTTP headers to the request.

    :type access_key: str
    :param access_key: (optional) IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: (optional) IA-S3 secret_key to use when making the given request.

    :type queue_derive: bool
    :param queue_derive: (optional) Set to False to prevent an item from being derived
                         after upload.

    :type verbose: bool
    :param verbose: (optional) Display upload progress.

    :type verify: bool
    :param verify: (optional) Verify local MD5 checksum matches the MD5 checksum of the
                   file received by IAS3.

    :type checksum: bool
    :param checksum: (optional) Skip uploading files based on checksum.

    :type delete: bool
    :param delete: (optional) Delete local file after the upload has been successfully
                   verified.

    :type retries: int
    :param retries: (optional) Number of times to retry the given request if S3 returns a
                    503 SlowDown error.

    :type retries_sleep: int
    :param retries_sleep: (optional) Amount of time to sleep between ``retries``.

    :type debug: bool
    :param debug: (optional) Set to True to print headers to stdout, and exit without
                  sending the upload request.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    """
    item = get_item(identifier)
    return item.upload(files, **kwargs)


# download()
# ________________________________________________________________________________________
def download(identifier, files=None, source=None, formats=None, glob_pattern=None,
             dry_run=None, clobber=None, no_clobber=None, checksum=None, destdir=None,
             no_directory=None, verbose=None, debug=None, **kwargs):
    """Download files from an item.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: (optional) Only return files matching the given file names.

    :param source: (optional) Only return files matching the given sources.

    :param formats: (optional) Only return files matching the given formats.

    :type glob_pattern: str
    :param glob_pattern: (optional) Only return files matching the given glob pattern.

    :type dry_run: bool
    :param dry_run: (optional) Print URLs to files to stdout rather than downloading
                    them.

    :type clobber: bool
    :param clobber: (optional) Overwrite local files if they already exist.

    :type no_clobber: bool
    :param no_clobber: (optional) Do not overwrite local files if they already exist.

    :type checksum: bool
    :param checksum: (optional) Skip downloading file based on checksum.

    :type destdir: bool
    :param destdir: (optional) Download files to the given directory.

    :type no_directory: bool
    :param no_directory: (optional) Download files to current working directory rather
                         than creating an item directory.

    :type verbose: bool
    :param verbose: (optional) Display download progress.

    :param \*\*kwargs: Optional arguments that ``get_item`` takes.

    """
    item = get_item(identifier, **kwargs)
    item.download(files, source, formats, glob_pattern, dry_run, clobber, no_clobber,
                  checksum, destdir, no_directory, verbose, debug)


# delete()
# ________________________________________________________________________________________
def delete(identifier, files=None, source=None, formats=None, glob_pattern=None,
           cascade_delete=None, access_key=None, secret_key=None, verbose=None,
           debug=None, **kwargs):
    """Delete files from an item. Note: Some system files, such as <itemname>_meta.xml,
    cannot be deleted.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier for a given item.

    :param files: (optional) Only return files matching the given filenames.

    :param source: (optional) Only return files matching the given sources.

    :param formats: (optional) Only return files matching the given formats.

    :type glob_pattern: str
    :param glob_pattern: (optional) Only return files matching the given glob pattern.

    :type cascade_delete: bool
    :param cascade_delete: (optional) Also deletes files derived from the file, and files
                           the filewas derived from.

    :type access_key: str
    :param access_key: (optional) IA-S3 access_key to use when making the given request.

    :type secret_key: str
    :param secret_key: (optional) IA-S3 secret_key to use when making the given request.

    :type verbose: bool
    :param verbose: Print actions to stdout.

    :type debug: bool
    :param debug: (optional) Set to True to print headers to stdout and exit exit without
                  sending the delete request.

    """
    files = get_files(identifier, files, source, formats, glob_pattern, **kwargs)

    responses = []
    for f in files:
        r = f.delete(
            cascade_delete=cascade_delete,
            access_key=access_key,
            secret_key=secret_key,
            verbose=verbose,
            debug=debug
        )
        responses.append(r)
    return responses


# get_tasks()
# ________________________________________________________________________________________
def get_tasks(identifier=None, task_ids=None, task_type=None, params=None, config=None,
              verbose=None):
    """Get tasks from the Archive.org catalog. ``internetarchive`` must be configured
    with your logged-in-* cookies to use this function. If no arguments are provided,
    all queued tasks for the user will be returned.

    :type identifier: str
    :param identifier: (optional) The Archive.org identifier for which to retrieve tasks
                       for.

    :type task_ids: int or str
    :param task_ids: (optional) The task_ids to retrieve from the Archive.org catalog.

    :type task_type: str
    :param task_type: (optional) The type of tasks to retrieve from the Archive.org
                      catalog. The types can be either "red" for failed tasks, "blue" for
                      running tasks, "green" for pending tasks, "brown" for paused tasks,
                      or "purple" for completed tasks.

    :type params: dict
    :param params: (optional) The URL parameters to send with each request sent to the
                   Archive.org catalog API.

    :type config: dict
    :param secure: (optional) Configuration options for session.

    :type verbose: bool
    :param verbose: (optional) Set to ``True`` to retrieve verbose information for each
                    catalog task returned. verbose is set to ``True`` by default.

    :returns: A set of :class:`CatalogTask` objects.

    """
    _catalog = catalog.Catalog(identifier=identifier, task_ids=task_ids, params=params,
                               config=config, verbose=verbose)
    if task_type:
        return eval('_catalog.{0}_rows'.format(task_type.lower()))
    else:
        return _catalog.tasks


# search_items()
# ________________________________________________________________________________________
def search_items(query, fields=None, params=None, config=None, v2=None):
    """Search for items on Archive.org.

    :type query: str
    :param query: The Archive.org search query to yield results for. Refer to
                  https://archive.org/advancedsearch.php#raw for help formatting your
                  query.

    :type fields: bool
    :param fields: (optional) The metadata fields to return in the search results.

    :type params: dict
    :param params: (optional) The URL parameters to send with each request sent to the
                   Archive.org Advancedsearch Api.

    :type config: dict
    :param secure: (optional) Configuration options for session.

    :type v2: bool
    :param v2: To use the archive.org/v2 Advancedsearch API, set v2 to ``True``.

    :returns: A :class:`Search` object, yielding search results.

    """
    return search.Search(query, fields=fields, params=params, config=config, v2=v2)
