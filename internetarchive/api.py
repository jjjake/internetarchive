from sys import stdout

from . import item, search, catalog


# get_item()
#_________________________________________________________________________________________
def get_item(identifier, metadata_timeout=None, config=None, max_retries=1):
    return item.Item(identifier, metadata_timeout, config, max_retries)

# get_files()
#_________________________________________________________________________________________
def get_files(identifier, files=None, source=None, formats=None, glob_pattern=None,
              metadata_timeout=None, config=None):
    item = get_item(identifier, metadata_timeout, config)
    return item.get_files(files, source, formats, glob_pattern)

# iter_files()
#_________________________________________________________________________________________
def iter_files(identifier, metadata_timeout=None, config=None):
    item = get_item(identifier, metadata_timeout, config)
    return item.iter_files()

# modify_metadata()
#_________________________________________________________________________________________
def modify_metadata(identifier, metadata, timeout=None, target='metadata', append=False):
    item = get_item(identifier, metadata_timeout=timeout)
    return item.modify_metadata(metadata, target, append=append)

# upload()
#_____________________________________________________________________________________
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
#_________________________________________________________________________________________
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
#_________________________________________________________________________________________
def delete(identifier, filenames=None, **kwargs):
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
    return search.Search(query, **kwargs)

# mine()
#_________________________________________________________________________________________
def get_data_miner(identifiers, **kwargs):
    from . import mine
    return mine.Mine(identifiers, **kwargs)
