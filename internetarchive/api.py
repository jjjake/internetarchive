from sys import stdout

from . import item, service



# get_item()
#_________________________________________________________________________________________
def get_item(identifier, **kwargs): 
    return item.Item(identifier, **kwargs)


# get_metadata()
#_________________________________________________________________________________________
def get_metadata(identifier, target=None, timeout=None): 
    item = get_item(identifier, metadata_timeout=timeout)
    return item.metadata.get(target, {}) if target else item.metadata


# get_files()
#_________________________________________________________________________________________
def get_files(identifier, timeout=None): 
    return get_metadata(identifier, target='files', timeout=timeout)


# iter_files()
#_________________________________________________________________________________________
def iter_files(identifier, timeout=None):
    item = get_item(identifier, metadata_timeout=timeout)
    return item.files()


# modify_metadata()
#_________________________________________________________________________________________
def modify_metadata(identifier, metadata, target='metadata'):
    item = get_item(identifier, metadata_timeout=timeout)
    return item.modify_metadata(metadata, target)


# upload_file()
#_____________________________________________________________________________________
def upload_file(identifier, local_file, **kwargs):
    item = get_item(identifier)
    return item.upload_file(identifier, local_file, **kwargs)
    

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
def download(identifier, **kwargs):
    """Download an item into the current working directory.

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
    item.download(**kwargs)


# download_file()
#_________________________________________________________________________________________
def download_file(identifier, filename, **kwargs):
    """

    Usage::

        >>> import internetarchive
        >>> internetarchive.download_file('stairs', 'stairs.avi')

    """
    item = get_item(identifier)
    remote_file = item.file(filename)
    stdout.write('downloading: {0}\n'.format(filename))
    remote_file.download(**kwargs)


# get_tasks()
#_________________________________________________________________________________________
def get_tasks(**kwargs): 
    catalog = service.Catalog(kwargs.get('params'))
    task_type = kwargs.get('task_type')
    if task_type:
        return eval('catalog.{0}_rows'.format(task_type.lower()))
    else:
        return catalog.tasks


# search()
#_________________________________________________________________________________________
def search(query, **kwargs): 
    return service.Search(query, **kwargs)


# mine()
#_________________________________________________________________________________________
def get_data_miner(identifiers, **kwargs): 
    from . import mine
    return mine.Mine(identifiers, **kwargs)
