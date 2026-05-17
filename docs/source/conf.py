# docs/source/conf.py (v1.1)
"""
Конфигурационный файл для сборщика документации Sphinx.
"""
import os
import sys

# Указываем путь к исходному коду проекта (на 2 уровня выше: docs/source -> docs -> корень)
sys.path.insert(0, os.path.abspath('../..'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'FireTrack'
copyright = '2026, Ralka'
author = 'Ralka'
release = '1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

# Подключаем расширения для автоматического парсинга Docstrings
extensions = [
    'sphinx.ext.autodoc',      # Собирает докстринги из кода
    'sphinx.ext.viewcode',     # Добавляет ссылки на исходный код
    'sphinx.ext.napoleon',     # Поддержка Google и NumPy стилей комментариев
]

templates_path = ['_templates']
exclude_patterns = []

language = 'ru'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# Используем красивую тему (убедись, что сделал pip install sphinx_rtd_theme)
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
