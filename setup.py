 
#from distutils.core import Extension
from setuptools import setup, Extension
import sys
import platform
import subprocess

# Compiling posixshmem.c if necessary

if sys.version_info[0] == 3 and sys.version_info[1] == 6:
    subprocess.run(["python", "apalis/multiprocessing/clinic36.py", "apalis/multiprocessing/posixshmem.c"])
elif sys.version_info[0] == 3 and sys.version_info[1] == 7:
    subprocess.run(["python", "apalis/multiprocessing/clinic37.py", "apalis/multiprocessing/posixshmem.c"])

if sys.version_info[0] == 3 and sys.version_info[1] < 8:
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

# Setup
with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
     name='apalis',
     version='0.1',
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
     python_requires='>=3.6',
     ext_modules=[module] if sys.version_info[1] < 8 else []
 )
