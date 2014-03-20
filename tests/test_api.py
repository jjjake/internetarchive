import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

from internetarchive.api import *

def test_api():
    # get_item()
    item = get_item('iacli-test-item')
    assert item.metadata['identifier'] == 'iacli-test-item'

    # get_files()
    files = get_files('nasa', 'nasa_meta.xml')
    assert files[0].name == 'nasa_meta.xml'

    md_files = ['nasa_meta.xml', 'nasa_files.xml']
    files = get_files('nasa', md_files)
    assert all(f.name in md_files for f in files)
    
    og_files = ['NASAarchiveLogo.jpg', 'globe_west_540.jpg']
    files = get_files('nasa', source='original')
    assert all(f.name in og_files for f in files)

    og_files = ['NASAarchiveLogo.jpg', 'globe_west_540.jpg']
    files = get_files('nasa', formats='Archive BitTorrent')
    assert files[0].name == 'nasa_archive.torrent'

    xml_files = ['nasa_meta.xml', 'nasa_reviews.xml', 'nasa_files.xml']
    files = get_files('nasa', glob_pattern='*xml')
    assert all(f.name in xml_files for f in files)

    # iter_files()
    file_generator = iter_files('nasa')
    assert not isinstance(file_generator, list)
    all_files = ['NASAarchiveLogo.jpg', 'globe_west_540.jpg', 'nasa_reviews.xml',
                 'nasa_meta.xml', 'nasa_archive.torrent', 'nasa_files.xml']
    assert all(f.name in all_files for f in list(file_generator))
