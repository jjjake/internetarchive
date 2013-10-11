"""Configure the `ia` CLI and internetarchive Python library.

usage:
    ia configure [--cookies]
    ia configure --help

options:
    -h, --help
    -c, --cookies  Add your IA cookies to configuration file.

"""
import os
from sys import stdout, exit

from docopt import docopt

from yaml import dump



# ia_configure()
#_________________________________________________________________________________________
def main(argv):
    args = docopt(__doc__, argv=argv)

    stdout.write(
        'Please visit https://archive.org/account/s3.php to retrieve your S3 keys\n\n')

    config = {
            's3': {
                'access_key': raw_input('Please enter your IA S3 access key: '),
                'secret_key': raw_input('Please enter your IA S3 secret key: '),
            }
    }

    if args['--cookies']:
        config['cookies'] = {
            'logged-in-user': raw_input('Please enter your logged-in-user cookie: '),
            'logged-in-sig': raw_input('Please Enter your logged-in-sig cookie: ')
    }

    configfile = dump(config, default_flow_style=False)
    configdir = os.path.join(os.environ['HOME'], '.config')
    if not os.path.isdir(configdir) and not os.path.isfile(configdir):
        os.mkdir(configdir)

    filename = ''
    if os.path.isdir(configdir):
        filename = os.path.join(configdir, 'internetarchive.yml')
    else:
        filename = os.path.join(os.environ['HOME'], '.internetarchive.yml')

    if os.path.exists(filename):
        overwrite = raw_input('\nYou already have an ia config file: '
                              '{0} \n\nWould you like to overwrite it?'
                              '[y/n] '.format(filename).lower())
        if overwrite not in ['y', 'yes']:
            stdout.write('\nExiting without overwriting config file!\n')
            exit(1)

    with open(filename, 'wb') as fp:
        os.chmod(filename, 0o700)
        fp.write(configfile)

    stdout.write('\nSuccessfully saved your new config to: {0}\n'.format(filename))
