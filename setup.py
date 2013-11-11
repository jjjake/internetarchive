from setuptools import setup
from sys import version_info, stderr, exit



extra = {}
if version_info >= (3,):
    stderr.write('Python3 is not yet supported.\n')
    exit(1)
    #extra['use_2to3'] = True

setup(
    name='internetarchive',
    version='0.4.5',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    packages=['internetarchive', 'iacli'],
    entry_points = {
        'console_scripts': [
            'ia = iacli.ia:main',
        ],
    },
    url='https://github.com/jjjake/ia-wrapper',
    license='LICENSE',
    description='A python interface to archive.org.',
    long_description=open('README.rst').read(),
    install_requires=[
        'requests==2.0.0',
        'jsonpatch==1.1',
        'pytest==2.3.4',
        'docopt==0.6.1',
        'PyYAML==3.10',
    ],
    dependency_links=[
        'https://github.com/downloads/surfly/gevent/gevent-1.0rc2.tar.gz#egg=gevent-1.0.rc2',
    ],
    extras_require = {
        'speedups': [
            'ujson==1.33',
            'Cython==0.18',
            'gevent==1.0rc2',
        ],
    },
    **extra
)
