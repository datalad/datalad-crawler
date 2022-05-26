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
