# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from datalad.support.annexrepo import AnnexRepo

from datalad.utils import chpwd
from datalad.utils import swallow_logs
from datalad.utils import make_tempfile

from logging import getLogger
lgr = getLogger('datalad.crawl.tests')


# This function needs to be in a file whose name starts with "test_" in order
# for pytest to do assertion rewriting on it.
def _test_smoke_pipelines(func, args, kwargs={}):
    with make_tempfile(mkdir=True) as tmpdir:
        AnnexRepo(tmpdir, create=True)
        with chpwd(tmpdir):
            with swallow_logs():
                for p in [func(*args, **kwargs)]:
                    assert len(p) > 1
