"""
Internet Archive Python Library documentation configuration.
"""

import os
import sys

import alabaster

import internetarchive
from internetarchive import __version__

# Add the project root to Python's module search path
sys.path.insert(0, os.path.abspath('../../'))

# -- Project information ----------------------------------------------------
project = 'internetarchive'
copyright = '2015, Internet Archive'

# The short X.Y version
version = __version__
# The full version, including alpha/beta/rc tags
release = version

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'alabaster',
    'sphinx_autodoc_typehints',
]

# Paths containing templates
templates_path = ['_templates']

# File extensions of source files
source_suffix = '.rst'

# Master document (starting point)
master_doc = 'index'

# Files to exclude
exclude_patterns: list[str] = []

# Don't prepend module names to titles
add_module_names = False

# Syntax highlighting style
pygments_style = 'sphinx'

# -- Intersphinx configuration ----------------------------------------------
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://docs.python-requests.org/en/latest/', None),
}

# -- Autodoc configuration --------------------------------------------------
autodoc_member_order = 'bysource'

# -- HTML output configuration ----------------------------------------------
html_theme_path = [alabaster.get_path()]
html_theme = 'alabaster'

html_theme_options = {
    'github_user': 'jjjake',
    'github_repo': 'internetarchive',
    'github_button': True,
    'show_powered_by': False,
    'sidebar_width': '200px',
}

html_sidebars = {
    '**': [
        'sidebarlogo.html',
        'about.html',
        'navigation.html',
        'usefullinks.html',
        'searchbox.html',
    ]
}

# Static files
html_static_path = ['_static']

# HTML help builder output name
htmlhelp_basename = 'internetarchivedoc'

# -- LaTeX output configuration ---------------------------------------------
latex_elements: dict[str, str] = {}

latex_documents = [
    ('index', 'internetarchive.tex', 'internetarchive Documentation',
     'Jacob M. Johnson', 'manual'),
]

# -- Manual page output configuration ---------------------------------------
man_pages = [
    ('index', 'internetarchive', 'internetarchive Documentation',
     ['Jacob M. Johnson'], 1)
]

# -- Texinfo output configuration -------------------------------------------
texinfo_documents = [
    ('index', 'internetarchive', 'internetarchive Documentation',
     'Jacob M. Johnson', 'internetarchive', 'One line description of project.',
     'Miscellaneous'),
]
