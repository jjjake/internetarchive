import re
import ast
from setuptools import setup
from codecs import open


_version_re = re.compile(r'__version__\s+=\s+(.*)')
with open('internetarchive/__init__.py', 'rb', 'utf-8') as f:
    version = str(ast.literal_eval(_version_re.search(f.read()).group(1)))

with open('README.rst', 'r', 'utf-8') as f:
    readme = f.read()
with open('HISTORY.rst', 'r', 'utf-8') as f:
    history = f.read()

setup(
    name='internetarchive',
    version=version,
    url='https://github.com/jjjake/ia-wrapper',
    license='AGPL 3',
    author='Jacob M. Johnson',
    author_email='jake@archive.org',
    description='A python interface to archive.org.',
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    zip_safe=False,
    packages=[
        'internetarchive',
        'internetarchive.iacli',
    ],
    entry_points = {
        'console_scripts': [
            'ia = internetarchive.iacli.ia:main',
        ],
    },
    install_requires=[
        'requests==2.3.0',
        'jsonpatch==0.4',
        'pytest==2.3.4',
        'docopt==0.6.1',
        'PyYAML==3.10',
        'clint==0.3.3',
        'six==1.4.1',
    ],
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
