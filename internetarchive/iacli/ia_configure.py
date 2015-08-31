"""Configure the `ia` CLI and internetarchive Python library.

usage:
    ia configure [--help]

options:
    -h, --help

"""
import os
import sys
from getpass import getpass
from six.moves import input

from docopt import docopt
import yaml
from requests.exceptions import HTTPError

from internetarchive.config import get_auth_config



# ia_configure()
# ________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    sys.stdout.write('Please enter your Archive.org credentials below to have your\n'
                     'Archive.org cookies and IA-S3 keys added to your config file.\n\n')

    username = input('Email address: ')
    password = getpass('Password: ')

    try:
        config = get_auth_config(username, password)
    except HTTPError as exc:
        sys.stderr.write('\n{0}\n'.format(str(exc)))
        sys.exit(1)

    configfile = yaml.dump(config, default_flow_style=False).encode('utf-8')
    configdir = os.path.join(os.environ['HOME'], '.config')
    if not os.path.isdir(configdir) and not os.path.isfile(configdir):
        os.mkdir(configdir)

    filename = ''
    if os.path.isdir(configdir):
        filename = os.path.join(configdir, 'internetarchive.yml')
    else:
        filename = os.path.join(os.environ['HOME'], '.internetarchive.yml')

    if os.path.exists(filename):
        overwrite = input('\nYou already have an ia config file: '
                          '{0} \n\nWould you like to overwrite it?'
                          '[y/n] '.format(filename).lower())
        if overwrite not in ['y', 'yes']:
            sys.stdout.write('\nExiting without overwriting config file!\n')
            sys.exit(1)

    with open(filename, 'wb') as fp:
        os.chmod(filename, 0o700)
        fp.write(configfile)

    sys.stdout.write('\nSuccessfully saved your new config to: {0}\n'.format(filename))
