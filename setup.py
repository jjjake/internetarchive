from setuptools import setup
import sys
from codecs import open
import re
import ast


_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('internetarchive/__init__.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))

with open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()
with open('HISTORY.rst', 'r', 'utf-8') as f:
    history = f.read()

install_requires = [
    'requests>=2.0.0,<3.0.0',
    'jsonpatch==0.4',
    'docopt>=0.6.0,<0.7.0',
    'clint>=0.4.0,<0.5.0',
    'six>=1.0.0,<2.0.0',
    'schema>=0.4.0,<0.5.0',
]
if sys.version_info <= (2, 7):
    install_requires.append(['pyopenssl', 'ndg-httpsclient', 'pyasn1'])

setup(
    name='internetarchive',
    version=version,
    url='https://github.com/jjjake/internetarchive',
    license='AGPL 3',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    description='A python interface to archive.org.',
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    zip_safe=False,
    packages=[
        'internetarchive',
        'internetarchive.cli',
    ],
    entry_points = {
        'console_scripts': [
            'ia = internetarchive.cli.ia:main',
        ],
    },
    install_requires=install_requires,
    classifiers=(
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
    )
)
