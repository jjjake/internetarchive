from distutils.core import setup

setup(
    name='internetarchive',
    version='0.1',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    packages=['internetarchive'],
    #scripts=['bin/stowe-towels.py'],
    url='https://github.com/jjjake/ia-wrapper',
    license='LICENSE.txt',
    description='A python interface to archive.org.',
    long_description=open('README.md').read(),
)
