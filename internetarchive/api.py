from . import item, service, ias3, utils



# get_item()
#_________________________________________________________________________________________
def get_item(identifier, **kwargs): 
    return item.Item(identifier, **kwargs)


# get_metadata()
#_________________________________________________________________________________________
def get_metadata(identifier, timeout=None): 
    return utils.get_item_metadata(identifier, target='metadata', timeout=timeout)


# get_files()
#_________________________________________________________________________________________
def get_files(identifier, timeout=None): 
    return utils.get_item_metadata(identifier, target='files', timeout=timeout)


# iter_files()
#_________________________________________________________________________________________
def iter_files(identifier): 
    _item = item.Item(identifier)
    return _item.files()


# modify_metadata()
#_________________________________________________________________________________________
def modify_metadata(identifier, metadata, target='metadata'):
    _item = item.Item(identifier)
    return _item.modify_metadata(metadata, target)


# upload()
#_________________________________________________________________________________________
def upload(identifier, files, **kwargs):
    """Upload files to an item. The item will be created if it
    does not exist.

    Usage::

        >>> import internetarchive
        >>> md = dict(mediatype='image', creator='Jake Johnson')
        >>> files = ['/path/to/image1.jpg', 'image2.jpg']
        >>> item = internetarchive.upload('identifier', files, md)
        True

    """

    _item = item.Item(identifier)
    return _item.upload(files, **kwargs)


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
    
    _item = item.Item(identifier)
    _item.download(**kwargs)


# download_file()
#_________________________________________________________________________________________
def download_file(identifier, filename, **kwargs):
    """

    Usage::

        >>> import internetarchive
        >>> internetarchive.download_file('stairs', 'stairs.avi')

    """
    _item = item.Item(identifier)
    remote_file = _item.file(filename)
    sys.stdout.write('downloading: {0}\n'.format(fname))
    remote_file.download(**kwargs)


# get_tasks()
#_________________________________________________________________________________________
def get_tasks(**kwargs): 
    catalog = service.Catalog(**kwargs)
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
    miner = mine.Mine(identifiers, **kwargs)
    return miner
