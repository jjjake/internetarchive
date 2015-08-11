from collections import defaultdict
from xml.dom.minidom import parseString
import re


# get_xml_text()
# ________________________________________________________________________________________
def get_xml_text(xml_str, tag_name=None, text=None):
    tag_name = 'Message' if not tag_name else tag_name
    text = '' if not text else text
    p = parseString(xml_str)
    elements = p.getElementsByTagName(tag_name)
    for e in elements:
        for node in e.childNodes:
            if node.nodeType == node.TEXT_NODE:
                text += node.data
    return text


# get_args_dict()
# ________________________________________________________________________________________
def get_args_dict(args):
    # Convert args list into a metadata dict.
    args = [] if not args else args
    metadata = defaultdict(list)
    for md in args:
        key, value = md.split(':', 1)
        assert value
        if value not in metadata[key]:
            metadata[key].append(value)

    for key in metadata:
        # Flatten single item lists.
        if len(metadata[key]) <= 1:
            metadata[key] = metadata[key][0]

    return metadata
