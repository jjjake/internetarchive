try:
    import ujson as json
except ImportError:
    import json
import urllib2



# get_item_metadata()
#_____________________________________________________________________________________
def get_item_metadata(identifier, target=None, timeout=None):
    """Get an item's metadata from the `Metadata API 
    <http://blog.archive.org/2013/07/04/metadata-api/>`__

    :rtype: dict
    :returns: Metadat API response.

    """
    url = 'https://archive.org/metadata/{0}'.format(identifier)
    api_response = urllib2.urlopen(url, timeout=timeout)
    metadata = json.loads(api_response.read())
    if target:
        metadata = metadata.get(target, {})
    return metadata
