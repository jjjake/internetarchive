import os, sys, shutil
inc_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, inc_path)

import yaml

import internetarchive.config

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

def test_config(tmpdir):
    test_conf_file = tmpdir.join('ia_test_conf.yml')
    with test_conf_file.open('w') as fp:
        fp.write(yaml.dump(test_conf, default_flow_style=True))
        
    # Test reading config from a given file.
    config = internetarchive.config.get_config(config_file=str(test_conf_file),
                                               config={'custom': 'test'})
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test-user'
    assert config['s3']['access_key'] == 'test-access'
    assert config['s3']['secret_key'] == 'test-secret'
    assert config['custom'] == 'test'

def test_no_config():
    os.environ['HOME'] = ''
    #config = internetarchive.config.get_config(config=test_conf)
    config = internetarchive.config.get_config()
    assert config == {}

def test_custom_config():
    os.environ['HOME'] = ''
    config = internetarchive.config.get_config(config=test_conf)
    assert config['cookies']['logged-in-sig'] == 'test-sig'
    assert config['cookies']['logged-in-user'] == 'test-user'
    assert config['s3']['access_key'] == 'test-access'
    assert config['s3']['secret_key'] == 'test-secret'
