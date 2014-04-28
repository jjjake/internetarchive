from sys import stdout

from . import item, search, catalog


# get_item()
#_________________________________________________________________________________________
def get_item(identifier, metadata_timeout=None, config=None):
    """
    Gets the archive.org item with the identifier Item.
    See the documentation for :class:`internetarchive.Item <Item>`
    for details.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier
                       for a given item.

    :type metadata_timeout: int
    :param metadata_timeout: (optional) Set a timeout for retrieving
                             an item's metadata.

    :type config: dict
    :param secure: (optional) Configuration options for session.

    :rtype: :class:`internetarchive.Item <Item>`
    :returns: A :class:`internetarchive.Item <Item>` object.

    """
    return item.Item(identifier, metadata_timeout, config)

# get_files()
#_________________________________________________________________________________________
def get_files(identifier, files=None, source=None, formats=None, glob_pattern=None,
              metadata_timeout=None, config=None):
    """Get a list of :class:`File <File>` objects in the item
    `identifier` filtered by the passed parameters.

    :type identifier: str
    :param identifier: The identifier for the item to retrieve
                       the files from.

    :type files: str, list, tuple, set
    :param files: A file or list of files to include in the
                  returned list.

    :type source: str, list, tuple, set
    :param source: A source or list of sources to include files
                   from.

    :type formats: str, list, tuple, set
    :param formats: A format or list of formats to include files
                    in those formats.

    :type glob_pattern: str
    :param glob_pattern: A glob pattern to match against the
                         filenames.

    :rtype: list
    :returns: A list of :class:`File <File>` objects.

    """
    item = get_item(identifier, metadata_timeout, config)
    return item.get_files(files, source, formats, glob_pattern)

# iter_files()
#_________________________________________________________________________________________
def iter_files(identifier, metadata_timeout=None, config=None):
    """Generator for iterating over files in an item.

    :type identifier: str
    :param identifier: The identifier of the item.

    :rtype: generator
    :returns: A generator that yields :class:`internetarchive.File
              <File>` objects.

    """

    item = get_item(identifier, metadata_timeout, config)
    return item.iter_files()

# modify_metadata()
#_________________________________________________________________________________________
def modify_metadata(identifier, metadata, timeout=None, target='metadata', append=False):
    """Modify the metadata of an existing item on Archive.org.

    Note: The Metadata Write API does not yet comply with the
    latest Json-Patch standard. It currently complies with `version 02
    <https://tools.ietf.org/html/draft-ietf-appsawg-json-patch-02>`__.

    :type identifier: str
    :param identifier: The identifier of the item.

    :type metadata: dict
    :param metadata: Metadata used to update the item.

    :type target: str
    :param target: (optional) Set the metadata target to update.

    :type priority: int
    :param priority: (optional) Set task priority.

    Usage::

        >>> import internetarchive

        >>> md = dict(new_key='new_value', foo=['bar', 'bar2'])
        >>> internetarchive.modify_metadata('mapi_test_item1', md)

    :rtype: dict
    :returns: A dictionary containing the status_code and response
              returned from the Metadata API.

    """

    item = get_item(identifier, metadata_timeout=timeout)
    return item.modify_metadata(metadata, target, append=append)

# upload()
#_____________________________________________________________________________________
def upload(identifier, files, **kwargs):
    """Upload files to an item. The item will be created if it
    does not exist.

    :type identifier: str
    :param identifier: the identifier of the item.

    :type files: str, list, set, tuple
    :param files: The filepaths or file-like objects to upload.

    :type kwargs: dict
    :param kwargs: The keyword arguments from the call to
                   upload_file().

    Usage::

        >>> import internetarchive
        >>> md = dict(mediatype='image', creator='Jake Johnson')
        >>> internetarchive.upload('identifier', '/path/to/image.jpg', metadata=md, queue_derive=False)
        True

    :rtype: bool
    :returns: True if the request was successful and all files were
              uploaded, False otherwise.

    """
    item = get_item(identifier)
    return item.upload(files, **kwargs)

# download()
#_________________________________________________________________________________________
def download(identifier, filenames=None, **kwargs):
    """Download an item into the current working directory.

    :type identifier: str
    :param identifier: the identifier of the item.

    :type filenames: str, list, set
    :param filenames: The filename(s) of the given file(s) to download.

    :type concurrent: bool
    :param concurrent: Download files concurrently if ``True``.

    :type source: str
    :param source: Only download files matching given source.

    :type formats: str
    :param formats: Only download files matching the given Formats.

    :type glob_pattern: str
    :param glob_pattern: Only download files matching the given glob
                         pattern

    :type ignore_existing: bool
    :param ignore_existing: Overwrite local files if they already
                            exist.

    :rtype: bool
    :returns: True if if files have been downloaded successfully.

    Usage::

        >>> import internetarchive
        >>> internetarchive.download('stairs', source=['metadata', 'original'])

    """
    item = get_item(identifier)
    if filenames:
        if not isinstance(filenames, (set, list)):
            filenames = [filenames]
        for fname in filenames:
            f = item.get_file(fname)
            f.download(**kwargs)
    else:
        item.download(**kwargs)

# delete()
#_________________________________________________________________________________________
def delete(identifier, filenames=None, **kwargs):
    """Delete a file from the Archive. Note: Some files -- such as
    <itemname>_meta.xml -- cannot be deleted.

    :type identifier: str
    :param identifier: the identifier of the item.

    :type debug: bool
    :param debug: Set to True to print headers to stdout and exit
                  exit without sending the delete request.

    :type verbose: bool
    :param verbose: Print actions to stdout.

    :type cascade_delete: bool
    :param cascade_delete: Also deletes files derived from the file,
                           and files the file was derived from.
    """

    item = get_item(identifier)
    if filenames:
        if not isinstance(filenames, (set, list)):
            filenames = [filenames]
        for f in item.iter_files():
            if not f.name in filenames:
                continue
            f.delete(**kwargs)

# get_tasks()
#_________________________________________________________________________________________
def get_tasks(**kwargs):
    """:todo: Write docstring for get_tasks"""
    _catalog = catalog.Catalog(identifier=kwargs.get('identifier'),
                               params=kwargs.get('params'),
                               task_ids=kwargs.get('task_ids'))
    task_type = kwargs.get('task_type')
    if task_type:
        return eval('_catalog.{0}_rows'.format(task_type.lower()))
    else:
        return _catalog.tasks

# search_items()
#_________________________________________________________________________________________
def search_items(query, **kwargs):
    """query: str
    :param query: The search string to send to the archive.org,
                  using the `Advanced Search
                  <https://archive.org/advancedsearch.php>`__
                  syntax.

    :type fields: list
    :param fields: (optional) The fields to return about each item.
                   By default, only returns the identifier.

    :type params: dict
    :param params: (optional) Additional parameters to pass with
                   the query.

    :type config: dict
    :param config: (optional) User configuration options.

    :rtype: :class:`internetarchive.Search <Search>`
    :returns: An iterator over the search results.
    """

    return search.Search(query, **kwargs)

# mine()
#_________________________________________________________________________________________
def get_data_miner(identifiers, **kwargs):
    """Makes a generator for an list of `(index, item)` where `item`
    is an instance of :class:`internetarchive.Item <Item>` containing
    metadata, and index is the index, for each id in `identifiers`.
    Note: this does not return the items in the same order as given
    in the identifiers list.
        
    :type identifiers: list
    :param identifiers: a list of identifiers to get the metadata of

    :type workers: int
    :param workers: the number of concurrent workers to have
                    fecthing the metadata

    :type max_requests: int, None
    :param max_requests: the number of times to try fetching the
                         metadata, in case there is something wrong
                         with requesting it

    :rtype: :class:`internetarchive.Mine <Mine>`
    :returns: An iterator over the `(index, item)` results.

    """

    from . import mine
    return mine.Mine(identifiers, **kwargs)
