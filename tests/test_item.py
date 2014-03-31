import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)


import internetarchive

def test_item():
    item = internetarchive.Item('nasa')
    assert item.metadata['identifier'] == 'nasa'


def test_file(tmpdir):
    with tmpdir.as_cwd():
        item = internetarchive.Item('nasa')
        filename = 'nasa_meta.xml'
        file = item.get_file(filename)
        file.download()
        assert unicode(os.stat(filename).st_size) == file.size


def test_download(tmpdir):
    with tmpdir.as_cwd():
        item = internetarchive.Item('nasa')
        item_dir = item.identifier
        item.download()
        assert os.path.exists(item_dir)
        assert os.path.exists(os.path.join(item_dir, item.identifier+'_meta.xml'))
