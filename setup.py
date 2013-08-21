from setuptools import setup



setup(
    name='internetarchive',
    version='0.1',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    packages=['internetarchive'],
    scripts=['bin/ia'],
    url='https://github.com/jjjake/ia-wrapper',
    license='LICENSE.txt',
    description='A python interface to archive.org.',
    long_description=open('README.md').read(),
    install_requires=[
        'boto==2.5.2',
        'jsonpatch==0.4',
        'filechunkio==1.5',
    ]
)
