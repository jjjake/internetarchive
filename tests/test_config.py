import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import yaml

import internetarchive.config

def test_config():
    test_conf = {
        'cookies': {
            'logged-in-sig': 'test-sig',
            'logged-in-user': 'test-user',
        },
        's3': {
            'access_key': 'test-access',
            'secret_key': 'test-secret',
        }
    }

    with open('ia_test_conf.yml', 'w') as fp:
        fp.write(yaml.dump(test_conf, default_flow_style=True))
        
    # Test reading config from a given file.
    config = internetarchive.config.get_config(config_file='ia_test_conf.yml',
                                               config={'custom': 'test'})
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test-user'
    assert config['s3']['access_key'] == 'test-access'
    assert config['s3']['secret_key'] == 'test-secret'
    assert config['custom'] == 'test'
    os.remove('ia_test_conf.yml')

    # Test no config.
    os.environ['HOME'] = ''
    #config = internetarchive.config.get_config(config=test_conf)
    config = internetarchive.config.get_config()
    assert config == {}

    # Test custom config.
    os.environ['HOME'] = ''
    config = internetarchive.config.get_config(config=test_conf)
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test-user'
    assert config['s3']['access_key'] == 'test-access'
    assert config['s3']['secret_key'] == 'test-secret'
