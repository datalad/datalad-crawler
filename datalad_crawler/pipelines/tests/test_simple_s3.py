# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from glob import glob

from datalad_crawler.pipelines.tests.test_utils import _test_smoke_pipelines as _tsp
from datalad.utils import chpwd
from datalad.utils import _path_
from datalad.tests.utils_pytest import eq_
from datalad.tests.utils_pytest import assert_false
from datalad.tests.utils_pytest import with_tempfile
from datalad.tests.utils_pytest import use_cassette
from datalad.tests.utils_pytest import externals_use_cassette
from datalad.tests.utils_pytest import skip_if_no_network
from datalad.tests.utils_pytest import ok_clean_git
from datalad.tests.utils_pytest import ok_file_under_git
from ..simple_s3 import pipeline
from datalad.api import crawl_init
from datalad.api import crawl
from datalad.api import create
from datalad.support.annexrepo import AnnexRepo
from datalad.downloaders.tests.utils import get_test_providers

import pytest

from logging import getLogger
lgr = getLogger('datalad.crawl.tests')


@pytest.mark.parametrize("func,args,kwargs", [
    (pipeline, ["b"], {}),
    # to_http everywhere just to make it faster by avoiding initiating datalad
    # special remote
    (pipeline, ["b"], dict(to_http=True, prefix="prefix")),
    (pipeline, ["b"], dict(to_http=True)),
    (pipeline, ["b"], dict(to_http=True, archive=True)),
    (pipeline, ["b"], dict(to_http=True, directory="subdataset", prefix="some/")),
])
def test_smoke_pipelines(func, args, kwargs):
    _tsp(pipeline, args, kwargs)

@with_tempfile
@skip_if_no_network
def _test_drop(path=None, *, drop_immediately):
    s3url = 's3://datalad-test0-nonversioned'
    providers = get_test_providers(s3url)  # to verify having s3 credentials
    # vcr tape is getting bound to the session object, so we need to
    # force re-establishing the session for the bucket.
    # TODO (in datalad): make a dedicated API for that, now too obscure
    _ = providers.get_status(s3url, allow_old_session=False)
    create(path)
    # unfortunately this doesn't work without force dropping since I guess vcr
    # stops and then gets queried again for the same tape while testing for
    # drop :-/
    with chpwd(path):
        crawl_init(
            template="simple_s3",
            args=dict(
                bucket="datalad-test0-nonversioned",
                drop=True,
                drop_force=True,  # so test goes faster
                drop_immediately=drop_immediately,
            ),
            save=True
        )
    if drop_immediately:
        # cannot figure out but taping that interaction results in
        # git annex addurl  error.  No time to figure it out
        # so we just crawl without vcr for now. TODO: figure out WTF
        with chpwd(path):
            crawl()
    else:
        with externals_use_cassette(
                'test_simple_s3_test0_nonversioned_crawl_ext'
                + ('_immediately' if drop_immediately else '')), \
                chpwd(path):
            crawl()
    # test that all was dropped
    repo = AnnexRepo(path, create=False)
    files = glob(_path_(path, '*'))
    eq_(len(files), 8)
    for f in files:
        assert_false(repo.file_has_content(f))


@use_cassette('test_simple_s3_test0_nonversioned_crawl')
def test_drop():
    _test_drop(drop_immediately=False)


@use_cassette('test_simple_s3_test0_nonversioned_crawl_immediately')
def test_drop_immediately():
    _test_drop(drop_immediately=True)


@with_tempfile
@use_cassette('test_simple_s3_test2_obscurenames_versioned_crawl')
@skip_if_no_network
def test_obscure_names(path=None):
    bucket = "datalad-test2-obscurenames-versioned"
    get_test_providers('s3://' + bucket)  # to verify having s3 credentials
    create(path)
    with externals_use_cassette('test_simple_s3_test2_obscurenames_versioned_crawl_ext'), \
         chpwd(path):
        crawl_init(template="simple_s3",
                   args=dict(bucket=bucket),
                   save=True
                   )
        crawl()
    # fun with unicode was postponed
    ok_clean_git(path, annex=True)
    for f in [
        'f &$=@:+,?;', "f!-_.*'( )", 'f 1', 'f [1][2]'
    ]:
        ok_file_under_git(path, f, annexed=True)
