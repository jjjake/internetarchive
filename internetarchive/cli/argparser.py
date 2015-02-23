from collections import defaultdict
import re


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
    # Convert args list into a metadata dict.
    metadata = defaultdict(list)
    for md in args:
        key, value = md.split(':', 1)
        if value not in metadata[key]:
            metadata[key].append(value)

    #for _key, value in metadata.items():
    for key in metadata:
        # Flatten single item lists.
        if len(metadata[key]) <= 1:
            metadata[key] = metadata[key][0]

    return metadata
