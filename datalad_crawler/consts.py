# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""constants for datalad_crawler
"""

from os.path import join

from datalad.consts import HANDLE_META_DIR
from datalad.consts import ARCHIVES_SPECIAL_REMOTE
from datalad.consts import DATALAD_SPECIAL_REMOTE

# directory containing prepared metadata of a dataset repository:
CRAWLER_META_DIR = join(HANDLE_META_DIR, 'crawl')
CRAWLER_META_CONFIG_FILENAME = 'crawl.cfg'
CRAWLER_META_CONFIG_PATH = join(CRAWLER_META_DIR, CRAWLER_META_CONFIG_FILENAME)
CRAWLER_META_VERSIONS_DIR = join(CRAWLER_META_DIR, 'versions')
# TODO: RENAME THIS UGLINESS?
CRAWLER_META_STATUSES_DIR = join(CRAWLER_META_DIR, 'statuses')
