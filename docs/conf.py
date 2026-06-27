# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------

project = 'MS Monitoring'
copyright = '2025, Diego Parrilla Calderón & Joaquín Ordieres-Meré'
author = 'Diego Parrilla Calderón & Joaquín Ordieres-Meré'
release = '0.1.0'   # must match the version in pyproject.toml

# -- General configuration ---------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.githubpages',
    'sphinx.ext.graphviz',
    'sphinx.ext.autosummary',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

autosummary_generate = True
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'private-members': True,
}
autodoc_mock_imports = [
    'influxdb_client',
    'psycopg2',
    'pandas',
    'pydantic',
    'pytz',
    'scipy',
    'sklearn',
]

language = 'en'

# -- Options for GitHub integration ------------------------------------------

html_context = {
    "display_github": True, # Integrate GitHub
    "github_user": "MultipleSclerosisMonitoring", # Username
    "github_repo": "DPC_2024", # Repo name
    "github_version": "main", # Version
    "conf_py_path": "/docs/", # Path in the checkout to the docs root
}

# -- Options for HTML output -------------------------------------------------

try:
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
except Exception:
    html_theme = 'alabaster'
    html_theme_path = []

html_static_path = ['_static']

rst_epilog = """
.. |a| unicode:: U+007C a U+007C
.. |g| unicode:: U+007C g U+007C
"""

