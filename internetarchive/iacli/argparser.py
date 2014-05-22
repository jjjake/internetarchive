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
    def contains_index(key):
        return re.search(r'\[\d+\]', key)

    def get_index(key):
        try:
            return int(re.search(r'(?<=\[)\d+(?=\])', key).group())
        except AttributeError:
            return 0

    def get_key_without_index(key):
        return re.split(r'\[\d+\]', key)[0]

    # Convert args list into a metadata dict.
    metadata = defaultdict(list)
    for md in args:
        key, value = md.split(':', 1)
        metadata[key].append(value)

    for _key, value in metadata.items():
        # Flatten single item lists.
        if len(value) <= 1:
            value = value[0]
            metadata[_key] = value

        # Insert support for elements, i.e. subject[1] = 'value1'
        if contains_index(_key):
            # Set the new key, removing the index.
            key = get_key_without_index(_key)
            del metadata[_key]
            if metadata.get(key):
                # Convert value to a list if the key already exists,
                # but it's value is not a list, set, or tuple.
                if not isinstance(metadata[key], (list, set, tuple)):
                    metadata[key] = [metadata[key]]
            else:
                metadata[key] = []
            metadata[key].append((get_index(_key), value))

    # Sort indexed items, and remove the index number.
    for key in metadata:
        if isinstance(metadata[key], (list, set, tuple)):
            if all(isinstance(x, tuple) for x in metadata[key]):
                value = sorted(metadata[key], key = lambda x: x[0])
                metadata[key] = [x[1] for x in value]

    return metadata
