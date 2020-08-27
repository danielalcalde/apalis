 
#from distutils.core import Extension
from setuptools import setup, Extension
from setuptools.command.install import install
from setuptools.command.egg_info import egg_info
from setuptools.command.develop import develop

import sys
import platform
import subprocess

# Setup
with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
     name='apalis',
     version='0.1.0.8',
     author="Daniel Alcalde Puente",
     author_email="daniel.alcaldepuente@rub.de",
     description="A parallel computing library.",
     long_description=long_description,
     long_description_content_type="text/markdown",
     url="https://github.com/danielalcalde/apalis",
     packages=["apalis", "apalis.multiprocessing"],
     license="MIT",
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: MIT License",
     ],
     install_requires=["numpy", "setproctitle", "psutil"],
     python_requires='>=3.8',
 )
