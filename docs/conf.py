# docs/conf.py (v1.0)
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

project = 'FireTrack'
copyright = '2026, FireTrack Team'
author = 'FireTrack Team'
release = '1.0.0'

# Добавляем расширения для генерации документации из Docstrings
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
