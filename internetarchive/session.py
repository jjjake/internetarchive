import os
import logging

import requests.sessions
import requests.cookies

import internetarchive.config
import internetarchive.item


class ArchiveSession(object):

    log_level = {
        'CRITICAL': 50,
        'ERROR':    40,
        'WARNING':  30,
        'INFO':     20,
        'DEBUG':    10,
        'NOTSET':   0,
    }

    FmtString = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # __init__()
    # ____________________________________________________________________________________
    def __init__(self, config=None):
        super(ArchiveSession, self).__init__()
        config = internetarchive.config.get_config(config)
        self.cookies = requests.cookies.cookiejar_from_dict(config.get('cookies', {}))
        if 'logged-in-user' not in self.cookies:
            self.cookies['logged-in-user'] = os.environ.get('IA_LOGGED_IN_USER')
        if 'logged-in-sig' not in self.cookies:
            self.cookies['logged-in-sig'] = os.environ.get('IA_LOGGED_IN_SIG')

        self.config = config
        self.secure = config.get('secure', False)

        s3_config = self.config.get('s3', {})
        self.access_key = s3_config.get(('access_key'), os.environ.get('IAS3_ACCESS_KEY'))
        self.secret_key = s3_config.get(('secret_key'), os.environ.get('IAS3_SECRET_KEY'))

        self.logging_config = config.get('logging', {})
        if self.logging_config:
            _level = self.log_level[self.logging_config.get('level', 'NOTSET')]
            log_file = 'internetarchive.log'
            self.set_file_logger(_level, log_file)

    # __init__()
    # ____________________________________________________________________________________
    def set_file_logger(self, log_level, path, logger_name='internetarchive'):
        """Convenience function to quickly configure any level of
        logging to a file.

        :type log_level: int
        :param log_level: A log level as specified in the `logging` module

        :type path: string
        :param path: Path to the log file. The file will be created
        if it doesn't already exist.

        """
        log = logging.getLogger(logger_name)
        log.setLevel(logging.DEBUG)
        fh = logging.FileHandler(path)
        fh.setLevel(log_level)
        formatter = logging.Formatter(self.FmtString)
        fh.setFormatter(formatter)
        log.addHandler(fh)


def get_session(config=None):
    """
    Return a new ArchiveSession object

    """
    return ArchiveSession(config)
