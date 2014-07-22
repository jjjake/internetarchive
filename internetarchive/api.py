from . import item, search, catalog


# get_item()
# ________________________________________________________________________________________
def get_item(identifier, metadata_timeout=None, config=None, max_retries=1,
             archive_session=None):
    """Get an :class:`internetarchive.item.Item <Item>` object.

    :type identifier: str
    :param identifier: The globally unique Archive.org identifier
                       for a given item.

    :type metadata_timeout: int
    :param metadata_timeout: (optional) Set a timeout for retrieving
                             an item's metadata.

    :type config: dict
    :param secure: (optional) Configuration options for session.

    :type max_retries: int
    :param max_retries: (optional) Maximum number of times to request
                        a website if the connection drops.

    """
    return item.Item(identifier, metadata_timeout, config, max_retries, archive_session)


# get_files()
# ________________________________________________________________________________________
def get_files(identifier, files=None, source=None, formats=None, glob_pattern=None,
              metadata_timeout=None, config=None):
    item = get_item(identifier, metadata_timeout, config)
    return item.get_files(files, source, formats, glob_pattern)


# iter_files()
# ________________________________________________________________________________________
def iter_files(identifier, metadata_timeout=None, config=None):
    item = get_item(identifier, metadata_timeout, config)
    return item.iter_files()


# modify_metadata()
# ________________________________________________________________________________________
def modify_metadata(identifier, metadata, timeout=None, target='metadata', append=False):
    item = get_item(identifier, metadata_timeout=timeout)
    return item.modify_metadata(metadata, target, append=append)


# upload()
# ____________________________________________________________________________________
def upload(identifier, files, **kwargs):
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
        >>> item.upload('/path/to/image.jpg', metadata=md, queue_derive=False)
        True

    :rtype: bool
    :returns: True if the request was successful and all files were
              uploaded, False otherwise.

    """
    item = get_item(identifier)
    return item.upload(files, **kwargs)


# download()
# ________________________________________________________________________________________
def download(identifier, filenames=None, **kwargs):
    """Download an item into the current working directory.

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
# ________________________________________________________________________________________
def delete(identifier, filenames=None, **kwargs):
    item = get_item(identifier)
    if filenames:
        if not isinstance(filenames, (set, list)):
            filenames = [filenames]
        for f in item.iter_files():
            if f.name not in filenames:
                continue
            f.delete(**kwargs)


# get_tasks()
# ________________________________________________________________________________________
def get_tasks(**kwargs):
    _catalog = catalog.Catalog(identifier=kwargs.get('identifier'),
                               params=kwargs.get('params'),
                               task_ids=kwargs.get('task_ids'))
    task_type = kwargs.get('task_type')
    if task_type:
        return eval('_catalog.{0}_rows'.format(task_type.lower()))
    else:
        return _catalog.tasks


# search_items()
# ________________________________________________________________________________________
def search_items(query, **kwargs):
    return search.Search(query, **kwargs)


# mine()
# ________________________________________________________________________________________
def get_data_miner(identifiers, **kwargs):
    from . import mine
    return mine.Mine(identifiers, **kwargs)
