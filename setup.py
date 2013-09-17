import sys
from setuptools import setup


setup(
    name='internetarchive',
    version="0.3.1",
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    packages=['internetarchive'],
    scripts=['bin/ia'],
    url='https://github.com/jjjake/ia-wrapper',
    license='LICENSE',
    description='A python interface to archive.org.',
    long_description=open('README.rst').read(),
    install_requires=[
        'boto==2.9.9',
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
)
