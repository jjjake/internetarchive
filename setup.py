from setuptools import setup


setup(
    name='internetarchive',
    version="0.2.7",
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
        'ujson==1.33',
        'pytest==2.3.4',
        'argparse==1.2.1',
    ]
)
