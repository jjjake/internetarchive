import requests
from requests.exceptions import ConnectionError



# get_item_metadata()
#_____________________________________________________________________________________
def get_item_metadata(identifier, target=None, timeout=None, secure=False):
    """Get an item's metadata from the `Metadata API 
    <http://blog.archive.org/2013/07/04/metadata-api/>`__

    :type identifier: str
    :param identifier: Globally unique Archive.org identifier.

    :type target: bool
    :param target: (optional) Metadata target to retrieve.

    :type timeout: int
    :param timeout: (optional) Set the timeout for the HTTP request.  
                    Note: this is usually not needed as the Metadata API 
                    is designed to timeout if any connection issues 
                    arrise.

    :type secure: bool
    :param secure: (optional) If secure is True, use HTTPS protocol, 
                   otherwise use HTTP.

    :rtype: dict
    :returns: Metadat API response.

    """
    url = 'http://archive.org/metadata/{0}'.format(identifier)
    if secure:
        url = url.replace('http', 'https')
    r = requests.get(url)
    if r.status_code != 200:
        raise ConnectionError("Unable connect to Archive.org "
                              "({0})".format(r.status_code))
    metadata = r.json()
    if target:
        metadata = metadata.get(target, {})
    return metadata
