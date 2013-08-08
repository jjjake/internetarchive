import os, sys
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import archive

def test_item():
    item = archive.Item('stairs')
    assert item.metadata['metadata']['identifier'] == 'stairs'


def test_file():
    item = archive.Item('stairs')
    filename = 'glogo.png'
    file = item.file(filename)

    assert not os.path.exists(filename)
    file.download()

    assert os.stat(filename).st_size == file.size
    os.unlink(filename)
