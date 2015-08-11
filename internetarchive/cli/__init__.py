from pkg_resources import iter_entry_points, load_entry_point


__all__ = [
    'ia_configure',
    'ia_delete',
    'ia_download',
    'ia_list',
    'ia_metadata',
    'ia_search',
    'ia_tasks',
    'ia_upload',
]


# Load internetarchive.cli plugins, and add to __all__.
for object in iter_entry_points(group='internetarchive.cli.plugins', name=None):
    __all__.append(object.name)
    globals()[object.name] = load_entry_point(
        object.dist, 'internetarchive.cli.plugins', object.name)
