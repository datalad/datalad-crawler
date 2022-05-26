# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil; coding: utf-8 -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from os.path import join as opj

from datalad_crawler.pipelines.tests.test_utils import _test_smoke_pipelines
from ...nodes.annex import (
    Annexificator,
    initiate_dataset,
)
from datalad.dochelpers import exc_str
from datalad.utils import chpwd
from datalad.utils import _path_
from datalad.support import path as op
from datalad.support.exceptions import MissingExternalDependency
from datalad.tests.utils_pytest import with_tree
from datalad.tests.utils_pytest import eq_, assert_in
from datalad.tests.utils_pytest import with_tempfile
from datalad.tests.utils_pytest import serve_path_via_http
from datalad.tests.utils_pytest import ok_file_has_content
from datalad.tests.utils_pytest import ok_file_under_git, ok_clean_git
from datalad.tests.utils_pytest import usecase
from datalad.tests.utils_pytest import swallow_logs
from ..simple_with_archives import pipeline
from datalad.api import create

from datalad.api import crawl, crawl_init

import pytest

import logging
from logging import getLogger
lgr = getLogger('datalad.crawl.tests')


def test_smoke_pipelines():
    _test_smoke_pipelines(pipeline, ["random_url"])

from .test_balsa import TEST_TREE1

# A little integration test

@with_tree(tree=TEST_TREE1, archives_leading_dir=False)
@serve_path_via_http
@with_tempfile
def test_simple1(ind=None, topurl=None, outd=None):

    list(initiate_dataset(
        template="simple_with_archives",
        dataset_name='test1',
        path=outd,
        add_fields={'url': topurl + 'study/show/WG33',
                    'a_href_match_': '.*download.*'}
    )({}))

    with chpwd(outd):
        out, stats = crawl()

    eq_(stats.add_annex, 3)

    ok_file_under_git(outd, 'file1.nii', annexed=True)
    ok_file_has_content(opj(outd, 'file1.nii'), 'content of file1.nii')

    ok_file_under_git(outd, _path_('dir1/file2.nii'), annexed=True)
    ok_file_has_content(opj(outd, 'dir1', 'file2.nii'), 'content of file2.nii')

    eq_(len(out), 1)


TEST_TREE2 = {
    '1.tar.gz': {
        'd': {"textfile": "1\n",
              "tooshort": "1"
              },
        "anothertext": "1 2 3",
    },
}
from datalad.support.external_versions import external_versions
import inspect
if (external_versions['datalad'] >= '0.11.2'
    # for the development state
    or 'decompress' in inspect.getargspec(ok_file_has_content)[0]):
    TEST_TREE2.update({
        # Also test handling of .gz files
        # Cannot be within a subdir without adding "matchers" to go into it
        # 'sd': {
        "compressed.dat.gz": u"мама мыла раму",
        # }
    })


@pytest.mark.parametrize("gz", [
    False,
    pytest.param(
        True,
        marks=pytest.mark.skipif(
            'compressed.dat.gz' not in TEST_TREE2,
            reason="datalad 0.11.2+ required",
        )
    ),
])
@usecase  # created with
@with_tree(tree=TEST_TREE2, archives_leading_dir=False)
@serve_path_via_http
@with_tempfile
def test_crawl_autoaddtext(ind=None, topurl=None, outd=None, *, gz):
    ds = create(outd)
    ds.run_procedure("cfg_text2git")
    with chpwd(outd):  # TODO -- dataset argument
        template_kwargs = {
            'url': topurl,
            'a_href_match_': '.*',
        }
        if gz:
            template_kwargs['archives_re'] = r"\.gz$"
        crawl_init(
            template_kwargs
            , save=True
            , template='simple_with_archives'
        )
        try:
            crawl()
        except MissingExternalDependency as exc:
            pytest.skip(exc_str(exc))
    ok_clean_git(outd)
    ok_file_under_git(outd, "anothertext", annexed=False)
    ok_file_under_git(outd, "d/textfile", annexed=False)
    ok_file_under_git(outd, "d/tooshort", annexed=True)

    if 'compressed.dat.gz' in TEST_TREE2:
        if gz:
            ok_file_under_git(outd, "compressed.dat", annexed=False)
            ok_file_has_content(op.join(outd, "compressed.dat"), u"мама мыла раму")
        else:
            ok_file_under_git(outd, "compressed.dat.gz", annexed=True)
    else:
        pytest.skip("Need datalad >= 0.11.2 to test .gz files decompression")


@with_tempfile(mkdir=True)
def test_warning_no_annex_but_incoming_pipeline(outd=None):
    with chpwd(outd):  # TODO -- dataset argument
        annex = Annexificator()
        incoming_pipeline = [[[annex]]]  # deep deep inside
        with swallow_logs(new_level=logging.WARNING) as cml:
            assert pipeline(incoming_pipeline=incoming_pipeline, annex=annex)
            assert not cml.out  # we did provide annex
            assert pipeline(incoming_pipeline=incoming_pipeline)
            assert_in("incoming_pipeline already contains annexificator", cml.out)
