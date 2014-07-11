try:
    from gevent import monkey, queue, spawn
    from gevent.hub import LoopExit
    monkey.patch_all(thread=False)
except ImportError:
    raise ImportError(
        """No module named gevent

        This feature requires the gevent neworking library. gevent
        and all of it's dependencies can be installed with pip:
        \tpip install cython gevent

        """)

from internetarchive import get_item
from internetarchive.session import get_session
from requests.exceptions import RequestException


# Mine class
# ________________________________________________________________________________________
class Mine(object):
    """This class is for concurrently retrieving metadata for items on
    Archive.org.

    Usage::

        >>> import internetarchive
        >>> miner = internetarchive.Mine(['identifier1', 'identifier2'], workers=50)
        >>> for md in miner:
        ...     print md

        """
    # __init__()
    # ____________________________________________________________________________________
    def __init__(self, identifiers, workers=20, max_requests=10):
        """Makes a generator for an list of `(index, item)` where `item`
        is an instance of `Item` containing metadata, and index is the index,
        for each id in `identifiers`. Note: this does not return the
        items in the same order as given in the identifiers list

        :type identifiers: list
        :param identifiers: a list of identifiers to get the metadata of
        :type workers: int
        :param workers: the number of concurrent workers to have fecthing the metadata
        :type max_requests: int or None
        :param max_requests: the number of times to try fetching the metadata,
        in case there is something wrong with requesting it

        :rtype: Mine

        """
        self.skips = []
        self.queue = queue
        self.workers = workers
        self.identifiers = identifiers
        self.item_count = len(identifiers)
        self.max_requests = max_requests
        self.queued_count = 0
        self.got_count = 0
        self.input_queue = self.queue.JoinableQueue(1000)
        self.json_queue = self.queue.Queue(1000)
        
        # Use the same session for each item fetch.
        self.session = get_session()

    # _metadata_getter()
    # ____________________________________________________________________________________
    def _metadata_getter(self):
        while True:
            i, identifier, num_requests = self.input_queue.get()
            try:
                item = get_item(identifier, archive_session=self.session)
                self.json_queue.put((i, item))
            except Exception as e:
                if (type(e) == RequestException and
                        (self.max_requests is None or num_requests < self.max_requests)):
                    self.input_queue.put((i, identifier, num_requests+1))
                else:
                    if identifier not in self.skips:
                        self.skips.append(identifier)
                    self.item_count -= 1
                    self.queued_count -= 1
                    if e.args is not None and len(e.args) > 0 and type(e.args[0]) == str:
                        e.args = ((e.args[0]+' when processing id '+repr(identifier),) +
                                  e.args[1:])
            finally:
                self.input_queue.task_done()

    # _queue_input()
    # ____________________________________________________________________________________
    def _queue_input(self):
        for i, identifier in enumerate(self.identifiers):
            if identifier not in self.skips:
                self.input_queue.put((i, identifier, 0))
                self.queued_count += 1

    # __iter__()
    # ____________________________________________________________________________________
    def __iter__(self):
        self.queued_count = 0
        self.got_count = 0
        spawn(self._queue_input)
        for i in range(self.workers):
            spawn(self._metadata_getter)

        def metadata_iterator_helper():
            while self.queued_count < self.item_count or self.got_count < self.queued_count:
                self.got_count += 1
                try:
                    yield self.json_queue.get()
                except LoopExit:
                    raise StopIteration

        return metadata_iterator_helper()
