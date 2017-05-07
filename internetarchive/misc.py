import datetime
from internetarchive import api


def uploaders_by_upload_counts(query, max_count=None, fields_to_include=('identifier',)):
    """List of uploaders, sorted by how many items they have uploaded.

Optionally include metadata fields from the item(s) found in the query.

Useful for identifying spam.
"""
    s = api.search_items(query, ['identifier'])
    uploaders = {}
    for i in s.iter_as_items():
        u = i.metadata.get('uploader')
        if u:
            x = uploaders.setdefault(u, [])
            if fields_to_include:
                x.append({f: i.metadata.get(f) for f in fields_to_include})
        else:
            print 'No uploader found: '+i.identifier
    ans = []
    for (k, v) in uploaders.items():
        count = len(api.search_items('uploader:"{}"'.format(k),
                                     params={'rows': 0}))
        if max_count is None or count < max_count:
            if fields_to_include:
                ans.append((count, k, v))
            else:
                ans.append((count, k))
    ans.sort()
    return ans

F = ('identifier', 'title', 'description')


def recent_uploads_by_uploader_count(minutes_back, max_count=100, fields_to_include=F):
    now = datetime.datetime.now()
    query = 'addeddate:[{:%Y-%m-%dT%H:%M:%SZ} TO {:%Y-%m-%dT%H:%M:%SZ}]'.format(
        now-datetime.timedelta(minutes=minutes_back), now)
    return uploaders_by_upload_counts(query, max_count, fields_to_include)
