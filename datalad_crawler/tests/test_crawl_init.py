# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##


from datalad.tests.utils_pytest import known_failure_direct_mode, eq_, assert_raises, assert_in
from mock import patch
from datalad.api import crawl_init
from collections import OrderedDict
from os.path import exists
from datalad.support.annexrepo import AnnexRepo
from datalad.tests.utils_pytest import with_tempfile, chpwd
from datalad.tests.utils_pytest import ok_clean_git
from datalad_crawler.consts import CRAWLER_META_CONFIG_PATH, CRAWLER_META_DIR
from datalad.distribution.dataset import Dataset

import pytest


@pytest.mark.parametrize("args,template,template_func,save,target_value", [
    (None, 'openfmri', 'superdataset_pipeline', False,
          '[crawl:pipeline]\ntemplate = openfmri\nfunc = superdataset_pipeline\n\n'),
    ({'dataset': 'ds000001'}, 'openfmri', None, False,
          '[crawl:pipeline]\ntemplate = openfmri\n_dataset = ds000001\n\n'),
    (['dataset=ds000001', 'versioned_urls=True'], 'openfmri', None, False,
          '[crawl:pipeline]\ntemplate = openfmri\n_dataset = ds000001\n_versioned_urls = True\n\n'),
    (None, 'openfmri', 'superdataset_pipeline', True,
          '[crawl:pipeline]\ntemplate = openfmri\nfunc = superdataset_pipeline\n\n'),
])
@with_tempfile(mkdir=True)
def test_crawl_init(tmpdir=None, *, args, template, template_func, save, target_value):
    ar = AnnexRepo(tmpdir, create=True)
    with chpwd(tmpdir):
        crawl_init(args=args, template=template, template_func=template_func, save=save)
        eq_(exists(CRAWLER_META_DIR), True)
        eq_(exists(CRAWLER_META_CONFIG_PATH), True)
        f = open(CRAWLER_META_CONFIG_PATH, 'r')
        contents = f.read()
        eq_(contents, target_value)
        if save:
            ds = Dataset(tmpdir)
            ok_clean_git(tmpdir, annex=isinstance(ds.repo, AnnexRepo))


@pytest.mark.parametrize("args,template,template_func,target_value", [
    ('tmpdir', None, None, ValueError),
    (['dataset=Baltimore', 'pie=True'], 'openfmri', None, RuntimeError),
    (None, None, None, TypeError),
])
@with_tempfile(mkdir=True)
def test_crawl_init_error(tmpdir=None, *, args, template, template_func, target_value):
        ar = AnnexRepo(tmpdir)
        with chpwd(tmpdir):
            assert_raises(target_value, crawl_init, args=args, template=template, template_func=template_func)


@pytest.mark.parametrize("return_value,exc,exc_msg", [
    ([], ValueError, "returned pipeline is empty"),
    ({1: 2}, ValueError, "pipeline should be represented as a list. Got: {1: 2}"),
])
@with_tempfile(mkdir=True)
def test_crawl_init_error_patch(d=None, *, return_value, exc, exc_msg):
    ar = AnnexRepo(d, create=True)
    with patch('datalad_crawler.crawl_init.load_pipeline_from_template',
               return_value=lambda dataset: return_value) as cm:
        with chpwd(d):
            with assert_raises(exc) as cm2:
                crawl_init(args=['dataset=Baltimore'], template='openfmri')
            assert_in(exc_msg, str(cm2.value))

            cm.assert_called_with('openfmri', None, return_only=True, kwargs=OrderedDict([('dataset', 'Baltimore')]))
