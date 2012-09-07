from distutils.core import setup

setup(
    name='ia-wrapper',
    version='0.1',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    packages=['archive'],
    #scripts=['bin/stowe-towels.py'],
    url='https://github.com/jjjake/ia-wrapper',
    license='LICENSE.txt',
    description='A simple python wrapper for the various archive.org APIs',
    long_description=open('README.md').read(),
)
