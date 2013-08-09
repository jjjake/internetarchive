import os, sys, shutil
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


def test_download():
    item = archive.Item('stairs')
    item_dir = item.identifier
    assert not os.path.exists(item_dir)
    item.download()
    assert os.path.exists(item_dir)
    assert os.path.exists(os.path.join(item_dir, item.identifier+'_meta.xml'))
    shutil.rmtree(item_dir)
