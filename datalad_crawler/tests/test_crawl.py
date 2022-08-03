# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Tests for crawl command

"""

__docformat__ = 'restructuredtext'

from mock import patch
from mock import call

from datalad.support.external_versions import external_versions

from datalad.api import crawl

from datalad.tests.utils_pytest import assert_cwd_unchanged
from datalad.tests.utils_pytest import assert_equal
from datalad.tests.utils_pytest import with_tempfile
from datalad.support.stats import ActivityStats
from datalad.utils import chpwd
from datalad.utils import getpwd
from datalad.utils import find_files
from datalad.utils import _path_


@assert_cwd_unchanged(ok_to_chdir=True)
@patch('datalad.utils.chpwd')
@patch('datalad_crawler.pipeline.load_pipeline_from_config', return_value=['pipeline'])
@patch('datalad_crawler.pipeline.run_pipeline', return_value=None)
# Note that order of patched things as args is reverse for some reason :-/
def test_crawl_api_chdir(run_pipeline_=None, load_pipeline_from_config_=None, chpwd_=None):
    output, stats = crawl('some_path_not_checked', chdir='somedir')
    assert_equal(stats, ActivityStats(datasets_crawled=1))  # nothing was done but we got it
    assert_equal(output, None)

    chpwd_.assert_called_with('somedir')
    load_pipeline_from_config_.assert_called_with('some_path_not_checked')
    run_pipeline_.assert_called_with(['pipeline'], stats=ActivityStats(datasets_crawled=1))


# XXX we could also mock run_pipeline to adjust stats etc more so we
#def run_pipeline_se(output, stats):
#    stats.add_git += 1
#    return output, stats


@assert_cwd_unchanged(ok_to_chdir=True)
@patch('datalad.utils.chpwd')
@patch('datalad.utils.get_logfilename', return_value="some.log")
@patch('datalad_crawler.pipeline.get_repo_pipeline_script_path', return_value='script_path')
@patch('datalad_crawler.pipeline.load_pipeline_from_config', return_value=['pipeline'])
@patch('datalad_crawler.pipeline.run_pipeline',
       side_effect=[
           [], [], [], [], Exception("crawling failed")
       ]
)
@patch('datalad.distribution.dataset.Dataset.subdatasets',  # return_value=['path1', 'path2'])
    side_effect=[
        ['path1', 'path1/path1_1', 'path2', 'path_to_fail'],
        # ATM we will not recursively crawl within sub-datasets
        # ['path1_1'],  # sub-dataset of the first sub-dataset
        #[],  # so it would get crawled and have no further sub-datasets
        # [],  # no sub-datasets in path2
        # will fail to return anything for path_to_fail
    ]
)
# Note that order of patched things as args is reverse for some reason :-/
@with_tempfile(mkdir=True)
def test_crawl_api_recursive(get_subdatasets_=None, run_pipeline_=None, load_pipeline_from_config_=None, get_repo_pipeline_script_path_=None,
                             get_lofilename_=None, chpwd_=None, tdir=None):
    pwd = getpwd()
    with chpwd(tdir):
        output, stats = crawl(recursive=True)
    assert_equal(pwd, getpwd())
    if external_versions['mock'] < '1.0.1':
        pytest.mark("needs a more recent mock which throws exceptions in side_effects")
    assert_equal(output, [[]]*4 + [None])  # for now output is just a list of outputs
    assert_equal(stats, ActivityStats(datasets_crawled=5, datasets_crawl_failed=1))  # nothing was done but we got it crawled
    chpwd_.assert_has_calls(
        [
            call(None),
            call('path1'),
            call('path1/path1_1'),
            call('path2'),
        ],
        any_order=True
    )
    assert_equal(list(find_files('.*', tdir, exclude_vcs=False)),
                 [_path_(tdir, 'some.log')])  # no files were generated besides the log
