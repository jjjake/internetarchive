import random

from gevent import monkey, queue, spawn
#monkey.patch_all(thread=False)
monkey.patch_all()

from internetarchive import Item



# Mine class
#_________________________________________________________________________________________
class Mine(object):
    """This class is for concurrently retrieving metadata for items on
    Archive.org.

    Usage::

        >>> import internetarchive
        >>> miner = internetarchive.Mine('itemlist.txt', workers=50)
        >>> for md in miner:
        ...     print md

    """
    # __init__()
    #_____________________________________________________________________________________
    def __init__(self, identifiers, workers=20):
        self.hosts = None
        self.skips = []
        self.queue = queue
        self.workers = workers
        self.done_queueing_input = False
        self.queued_count = 0
        self.identifiers = identifiers
        self.input_queue = self.queue.JoinableQueue(1000)
        self.json_queue = self.queue.Queue(1000)


    # _metadata_getter()
    #_____________________________________________________________________________________
    def _metadata_getter(self):
        while True:
            i, identifier = self.input_queue.get()
            if self.hosts:
                host = self.hosts[random.randrange(len(self.hosts))]
                while host in self.skips:
                    host = self.hosts[random.randrange(len(self.hosts))]
            else:
                host = None
            try:
                item = Item(identifier, host=host)
                self.json_queue.put((i, item))
            except:
                if host:
                    sys.stderr.write('host failed: {0}\n'.format(host))
                    self.skips.append(host)
                self.input_queue.put((i, identifier))
            finally:
                self.input_queue.task_done()


    # _queue_input()
    #_____________________________________________________________________________________
    def _queue_input(self):
        for i, identifier in enumerate(self.identifiers):
            self.input_queue.put((i, identifier))
            self.queued_count += 1
        self.done_queueing_input = True


    # items()
    #_____________________________________________________________________________________
    def items(self):
        spawn(self._queue_input)
        for i in range(self.workers):
            spawn(self._metadata_getter)

        def metadata_iterator_helper():
            got_count = 0
            while True:
                if self.done_queueing_input and got_count == self.queued_count:
                    break
                yield self.json_queue.get()
                got_count += 1

        return metadata_iterator_helper()
