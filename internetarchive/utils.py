import requests



# get_item_metadata()
#_____________________________________________________________________________________
def get_item_metadata(identifier, target=None, timeout=None):
    """Get an item's metadata from the `Metadata API 
    <http://blog.archive.org/2013/07/04/metadata-api/>`__

    :rtype: dict
    :returns: Metadat API response.

    """
    url = 'https://archive.org/metadata/{0}'.format(identifier)
    r = requests.get(url)
    metadata = r.json()
    if target:
        metadata = metadata.get(target, {})
    return metadata
