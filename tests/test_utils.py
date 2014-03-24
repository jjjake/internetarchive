import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import internetarchive.utils

def test_utils():
    cg = list(internetarchive.utils.chunk_generator(open('setup.py'), 10))
    ifp = internetarchive.utils.IterableToFileAdapter([1, 2], 200)
    assert len(ifp) == 200
    ifp.read()
