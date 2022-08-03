# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

import os
from glob import glob
from os.path import join as opj, exists

from ...pipeline import run_pipeline, FinishPipeline

from ...nodes.annex import Annexificator, initiate_dataset

from datalad.support.stats import ActivityStats
from datalad.support.gitrepo import GitRepo

from datalad.utils import chpwd
from datalad.tests.utils_pytest import with_tree
from datalad.tests.utils_pytest import eq_, assert_not_equal, ok_, assert_raises
from datalad.tests.utils_pytest import assert_in, assert_not_in
from datalad.tests.utils_pytest import skip_if_no_module
from datalad.tests.utils_pytest import with_tempfile
from datalad.tests.utils_pytest import serve_path_via_http
from datalad.tests.utils_pytest import skip_if_no_network
from datalad.tests.utils_pytest import use_cassette
from datalad.tests.utils_pytest import ok_file_has_content
from datalad.tests.utils_pytest import ok_file_under_git
from datalad.distribution.dataset import Dataset
from datalad.distribution.dataset import Dataset
from datalad_crawler.consts import CRAWLER_META_CONFIG_PATH

from datalad.api import crawl
from ..openfmri import superdataset_pipeline as ofcpipeline

from logging import getLogger
lgr = getLogger('datalad.crawl.tests')

# if we decide to emulate change (e.g. new dataset added)
_PLUG_HERE = '<!-- PLUG HERE -->'


@with_tree(tree={
    'index.html': """<html><body>
                        <a href="/dataset/ds000001/">ds001</a>
                        <a href="/dataset/ds000002/">ds002</a>
                        %s
                      </body></html>""" % _PLUG_HERE,
    },
)
@serve_path_via_http
@with_tempfile
def test_openfmri_superdataset_pipeline1(ind=None, topurl=None, outd=None):

    list(initiate_dataset(
        template="openfmri",
        template_func="superdataset_pipeline",
        template_kwargs={'url': topurl},
        path=outd,
    )())

    with chpwd(outd):
        crawl()
        #pipeline = ofcpipeline(url=topurl)
        #out = run_pipeline(pipeline)
    #eq_(out, [{'datalad_stats': ActivityStats()}])

    # TODO: replace below command with the one listing subdatasets
    subdatasets = ['ds000001', 'ds000002']
    eq_(Dataset(outd).subdatasets(fulfilled=True, result_xfm='relpaths'),
        subdatasets)

    # Check that crawling configuration was created for every one of those
    for sub in subdatasets:
        repo = GitRepo(opj(outd, sub))
        assert(not repo.dirty)
        assert(exists(opj(repo.path, CRAWLER_META_CONFIG_PATH)))

    # TODO: check that configuration for the crawler is up to the standard
    # Ideally should also crawl some fake datasets I guess
