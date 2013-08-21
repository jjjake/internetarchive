from setuptools import setup



setup(
    name='internetarchive',
    version='0.24',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    packages=['internetarchive'],
    scripts=['bin/ia'],
    url='https://github.com/jjjake/ia-wrapper',
    license='LICENSE',
    description='A python interface to archive.org.',
    long_description=open('README.rst').read(),
    install_requires=[
        'ujson',
        'boto==2.9.9',
        'jsonpatch==1.1',
        'filechunkio==1.5',
    ]
)
