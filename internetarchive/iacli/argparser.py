from collections import defaultdict



# get_xml_text()
#_________________________________________________________________________________________
def get_xml_text(elements, text=''):
    """:todo: document ``get_xml_text()`` function."""
    for e in elements:
        for node in e.childNodes:
            if node.nodeType == node.TEXT_NODE:
                text += node.data
    return text


# get_args_dict()
#_________________________________________________________________________________________
def get_args_dict(args):
    metadata = defaultdict(list)
    for md in args:
        key, value = md.split(':', 1)
        metadata[key].append(value)
    # Flatten single item lists.
    for key, value in metadata.items():
        if len(value) <= 1:
            metadata[key] = value[0]
    return metadata
