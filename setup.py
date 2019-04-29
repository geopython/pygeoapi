# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2018 Tom Kralidis
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

import io
import os
import re
from setuptools import Command, find_packages, setup
import shutil
import sys


class PyCleanBuild(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        remove_files = [
            'debian/files',
            'debian/python-pygeoapi.debhelper.log',
            'debian/python-pygeoapi.postinst.debhelper',
            'debian/python-pygeoapi.prerm.debhelper',
            'debian/python-pygeoapi.substvars'
        ]

        remove_dirs = [
            'debian/python-pygeoapi'
        ]

        for file_ in remove_files:
            try:
                os.remove(file_)
            except OSError:
                pass

        for dir_ in remove_dirs:
            try:
                shutil.rmtree(dir_)
            except OSError:
                pass

        for file_ in os.listdir('..'):
            if file_.endswith(('.deb', '.build', '.changes')):
                os.remove('../{}'.format(file_))


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess
        errno = subprocess.call([sys.executable,
                                 'pygeoapi/tests/run_tests.py'])
        raise SystemExit(errno)


class PyCoverage(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import subprocess

        errno = subprocess.call(['coverage', 'run', '--source=pygeoapi',
                                 '-m', 'unittest',
                                 'pygeoapi.tests.run_tests'])
        errno = subprocess.call(['coverage', 'report', '-m'])
        raise SystemExit(errno)


def read(filename, encoding='utf-8'):
    """read file contents"""
    full_path = os.path.join(os.path.dirname(__file__), filename)
    with io.open(full_path, encoding=encoding) as fh:
        contents = fh.read().strip()
    return contents


def get_package_version():
    """get version from top-level package init"""
    version_file = read('pygeoapi/__init__.py')
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


try:
    import pypandoc
    LONG_DESCRIPTION = pypandoc.convert('README.md', 'rst')
except(IOError, ImportError, OSError):
    print('Conversion to rST failed.  Using default (will look weird on PyPI)')
    LONG_DESCRIPTION = read('README.md')

DESCRIPTION = 'pygeoapi provides an API to geospatial data'

if os.path.exists('MANIFEST'):
    os.unlink('MANIFEST')

setup(
    name='pygeoapi',
    version=get_package_version(),
    description=DESCRIPTION.strip(),
    long_description=LONG_DESCRIPTION,
    license='MIT',
    platforms='all',
    keywords=' '.join([
        'geospatial',
        'data',
        'api'
    ]),
    author='Tom Kralidis',
    author_email='tomkralidis@gmail.com',
    maintainer='Tom Kralidis',
    maintainer_email='tomkralidis@gmail.com',
    url='https://pygeoapi.io',
    install_requires=read('requirements.txt').splitlines(),
    packages=find_packages(exclude=['pygeoapi.tests']),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'pygeoapi=pygeoapi:cli',
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: GIS'
    ],
    cmdclass={
        'test': PyTest,
        'coverage': PyCoverage,
        'cleanbuild': PyCleanBuild
    }
)
