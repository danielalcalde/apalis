 
#from distutils.core import Extension
from setuptools import setup, Extension
from setuptools.command.install import install
from setuptools.command.egg_info import egg_info
from setuptools.command.develop import develop

import sys
import platform
import subprocess


module = Extension(
    "apalis/multiprocessing/_posixshmem",
    define_macros=[
        ("HAVE_SHM_OPEN", "1"),
        ("HAVE_SHM_UNLINK", "1"),
        ("HAVE_SHM_MMAN_H", 1),
    ],
    libraries=["rt"],
    sources=["apalis/multiprocessing/posixshmem.c"]
    )

ext_modules = [module]

def custom_command():
    if sys.version_info[0] == 3 and sys.version_info[1] == 6:
        subprocess.run(["python", "apalis/multiprocessing/clinic36.py", "apalis/multiprocessing/posixshmem.c"])
    elif sys.version_info[0] == 3 and sys.version_info[1] == 7:
        subprocess.run(["python", "apalis/multiprocessing/clinic37.py", "apalis/multiprocessing/posixshmem.c"])

# For python <3.8 posixshmem.c needs to be compiled
class CustomInstallCommand(install):
    def run(self):
        custom_command()
        install.run(self)

class CustomDevelopCommand(develop):
    def run(self):
        custom_command()
        develop.run(self)
        
class CustomEggInfoCommand(egg_info):
    def run(self):
        custom_command()
        egg_info.run(self)
        
# Setup
with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
     name='apalis',
     version='0.1.0.7',
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
     python_requires='<3.8',
     cmdclass={
         'install': CustomInstallCommand,
         'develop': CustomDevelopCommand,
         'egg_info': CustomEggInfoCommand,
         },
     ext_modules=ext_modules
 )
