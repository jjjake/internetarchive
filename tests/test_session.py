import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

from internetarchive.session import get_session

def test_session():
    s = get_session()
    s.set_file_logger(0, 'test.log')
    os.remove('test.log')
