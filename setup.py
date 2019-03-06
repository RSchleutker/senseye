# -*- coding: utf-8 -*-
"""
Created on Sun Mar  3 10:51:39 2019

@author: Raphael
"""

from setuptools import setup

setup(name = 'senseye',
      version = '0.1',
      description = 'A lightweight module for monitoring Bluemaestro sensors',
      url = '',
      author = 'Raphael Schleutker',
      author_email = 'raphaelschleutker@gmx.de',
      packages = ['senseye'],
      zip_safe = False,
      install_requires = [
              'sqlalchemy',
              'werkzeug'
              ])