"""DataLad crawler extension"""

__docformat__ = 'restructuredtext'

from .version import __version__

# defines a datalad command suite
# this symbold must be identified as a setuptools entrypoint
# to be found by datalad
command_suite = (
    # description of the command suite, displayed in cmdline help
    "Crawl web resources",
    [
        # specification of a command, any number of commands can be defined
        (
            # importable module that contains the command implementation
            'datalad_crawler.crawl',
            # name of the command class implementation in above module
            'Crawl',
            'crawl',
        ),
        (
            # importable module that contains the command implementation
            'datalad_crawler.crawl_init',
            # name of the command class implementation in above module
            'CrawlInit',
            'crawl-init',
            'crawl_init',
        ),
    ]
)

import datalad.tests.utils
from datalad import setup_package as _setup_package
from datalad import teardown_package as _teardown_package

_datalad_default_branch = datalad.tests.utils.DEFAULT_BRANCH


def setup_package():
    # Q&D workaround for not messing for now with datalad specifying default
    # branch to be not master
    datalad.tests.utils.DEFAULT_BRANCH = 'master'
    return _setup_package()


def teardown_package():
    datalad.tests.utils.DEFAULT_BRANCH = _datalad_default_branch
    return _teardown_package()