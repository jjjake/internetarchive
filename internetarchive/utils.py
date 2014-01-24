def chunk_generator(fp, chunk_size):
    while True:
        chunk = fp.read(chunk_size)
        if not chunk:
            break
        yield chunk

class IterableToFileAdapter(object):
    def __init__(self, iterable, size):
        self.iterator = iter(iterable)
        self.length = size

    def read(self, size=-1): # TBD: add buffer for `len(data) > size` case
        return next(self.iterator, b'')

    def __len__(self):
        return self.length
