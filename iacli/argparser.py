from collections import defaultdict



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
