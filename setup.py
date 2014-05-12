from setuptools import setup
import sys


setup(
    name='internetarchive',
    version='0.5.9',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    packages=['internetarchive', 'internetarchive.iacli'],
    entry_points = {
        'console_scripts': [
            'ia = internetarchive.iacli.ia:main',
        ],
    },
    url='https://github.com/jjjake/ia-wrapper',
    license='LICENSE',
    description='A python interface to archive.org.',
    long_description=open('README.rst').read(),
    install_requires=[
        'requests==2.2.0',
        'jsonpatch==0.4',
        'pytest==2.3.4',
        'docopt==0.6.1',
        'PyYAML==3.10',
        'clint==0.3.3',
        'six==1.4.1',
    ],
    extras_require = {
        'speedups': [
            'ujson==1.33',
            'Cython==0.18',
            'gevent==1.0',
        ],
    },
)
