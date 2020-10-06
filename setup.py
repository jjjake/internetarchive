import re
from ast import literal_eval
from codecs import open

from setuptools import setup

_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('internetarchive/__init__.py', 'rb') as f:
    version = str(literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

with open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()
with open('HISTORY.rst', 'r', 'utf-8') as f:
    history = f.read()

setup(
    name='internetarchive',
    version=version,
    url='https://github.com/jjjake/internetarchive',
    license='AGPL 3',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    description='A Python interface to archive.org.',
    long_description=readme,
    include_package_data=True,
    zip_safe=False,
    packages=[
        'internetarchive',
        'internetarchive.cli',
    ],
    entry_points={
        'console_scripts': [
            'ia = internetarchive.cli.ia:main',
        ],
    },
    install_requires=[
        'requests>=2.9.1,<3.0.0',
        'jsonpatch>=0.4',
        'docopt>=0.6.0,<0.7.0',
        'tqdm>=4.0.0',
        'six>=1.13.0,<2.0.0',
        'schema>=0.4.0',
        'backports.csv < 1.07;python_version<"3.4"',
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ]
)
