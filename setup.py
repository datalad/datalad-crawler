#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages
from setuptools import findall

from os.path import join as opj
from os.path import sep as pathsep
from os.path import splitext
from os.path import dirname

from setup_support import BuildManPage
from setup_support import BuildRSTExamplesFromScripts
from setup_support import get_version


def findsome(subdir, extensions):
    """Find files under subdir having specified extensions

    Leading directory (datalad) gets stripped
    """
    return [
        f.split(pathsep, 1)[1] for f in findall(opj('datalad_crawler', subdir))
        if splitext(f)[-1].lstrip('.') in extensions
    ]

# extension version
version = get_version()

cmdclass = {
    'build_manpage': BuildManPage,
    'build_examples': BuildRSTExamplesFromScripts,
}

with open(opj(dirname(__file__), 'README.md')) as fp:
    long_description = fp.read()

requires = {
    'core': [
        'datalad>=0.14.0',
        'datalad_deprecated',
        'scrapy>=1.1.0',  # versioning is primarily for python3 support
    ],
    'devel-docs': [
        # Documentation
        'sphinx',
        'sphinx-rtd-theme',
    ],
    'tests': [
        'datalad>=0.17.0',
        'pytest>=7.0',
        'pytest-cov',
        'mock',
    ],
}
requires['devel'] = sum(list(requires.values()), [])

setup(
    # basic project properties can be set arbitrarily
    name="datalad_crawler",
    author="The DataLad Team and Contributors",
    author_email="team@datalad.org",
    version=version,
    description="DataLad extension package for crawling external web resources into an automated data distribution",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=[pkg for pkg in find_packages('.') if pkg.startswith('datalad')],
    # datalad command suite specs from here
    install_requires=requires['core'],
    extras_require=requires,
    cmdclass=cmdclass,
    entry_points = {
        # 'datalad.extensions' is THE entrypoint inspected by the datalad API builders
        'datalad.extensions': [
            # the label in front of '=' is the command suite label
            # the entrypoint can point to any symbol of any name, as long it is
            # valid datalad interface specification (see demo in this extension)
            'crawler=datalad_crawler:command_suite',
        ],
        'datalad.tests': [
            'crawler=datalad_crawler',
        ],
    },
)
