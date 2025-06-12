# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'MS_Activity_Movement'
copyright = '2025, Diego Parrilla Calderón & Joaquín Ordieres-Meré'
author = 'Diego Parrilla Calderón & Joaquín Ordieres-Meré'
release = '00.00.02'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
'sphinx.ext.autodoc',
'sphinx.ext.viewcode',
'sphinx.ext.napoleon',
'sphinx.ext.intersphinx',
'sphinx.ext.githubpages',
'sphinx.ext.graphviz',
'sphinx.ext.autosummary'
]

myst_enable_extensions = [
    "amsmath",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

autosummary_generate = True  # Habilita la generación automática de resúmenes
autodoc_default_options = {
    'members': True,          # Incluye todos los miembros (clases, funciones, etc.)
    'undoc-members': True,    # Incluye miembros no documentados
    'private-members': True,  # Incluye miembros privados (_nombre)
}

language = 'es'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
