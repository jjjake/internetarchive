import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import pytest

try:
    import internetarchive.mine
    py_test_mine = True
except ImportError:
    py_test_mine = False

@pytest.mark.skipif('py_test_mine == False', reason='requires internetarchive[speedups]')
def test_mine():
    def general_tests(ids):
        miner = internetarchive.mine.Mine(ids)
        results = list(miner)
        assert len(miner.identifiers) == len(results) + len(miner.skips)
        
        for id_ind, identifier in enumerate(miner.identifiers):
            assert (identifier in miner.skips or ((id_ind, identifier) in ((item_ind, item.identifier) for item_ind, item in results)))
            
    general_tests([])
    general_tests(['nasa', 'sbaiuvb%%', 2566])
    general_tests(['%%'])


@pytest.mark.skipif('py_test_mine == False', reason='requires internetarchive[speedups]')
def test_good_ids():
    ids = ['ozmaofoz00486gut', 'ozma_of_oz_librivox',
           'theemeraldcityof00517gut', 'emerald_city_librivox',
           'tiktokofoz00956gut', 'tik-tok_oz_librivox',
           'rinkitinkinoz00958gut', 'rinkitink_oz_jb_librivox']

    miner = internetarchive.mine.Mine(ids)
    results = [result for i, result in sorted(miner, key=lambda x: x[0])]
    for item, ident in zip(results, ids):
        assert item.metadata['identifier'] == ident


@pytest.mark.skipif('py_test_mine == False', reason='requires internetarchive[speedups]')
def test_bad_ids():
    bad_ids = ['%%', '../cow']
    
    bad_miner = internetarchive.mine.Mine(bad_ids)
    # because it's mining, it should just skip over what it can't handle:
    bad_results = list(bad_miner)
    # ... and it shouldn't return anything:
    assert len(bad_results) == 0
    # ... and it should record what it skips (i.e. everything):
    assert set(bad_miner.skips) == set(bad_ids)
