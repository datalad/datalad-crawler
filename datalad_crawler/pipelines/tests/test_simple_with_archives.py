# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from datalad.tests.utils import known_failure_direct_mode


from os.path import join as opj

from datalad_crawler.pipelines.tests.utils import _test_smoke_pipelines
from ...nodes.annex import initiate_dataset
from datalad.utils import chpwd
from datalad.utils import _path_
from datalad.tests.utils import with_tree
from datalad.tests.utils import eq_, assert_not_equal, ok_, assert_raises
from datalad.tests.utils import with_tempfile
from datalad.tests.utils import serve_path_via_http
from datalad.tests.utils import ok_file_has_content
from datalad.tests.utils import ok_file_under_git, ok_clean_git
from datalad.tests.utils import usecase
from datalad.tests.utils import known_failure_v6
from ..simple_with_archives import pipeline
from datalad.api import create

from datalad.api import crawl, crawl_init

from logging import getLogger
lgr = getLogger('datalad.crawl.tests')


def test_smoke_pipelines():
    yield _test_smoke_pipelines, pipeline, ["random_url"]

from .test_balsa import TEST_TREE1

# A little integration test

@with_tree(tree=TEST_TREE1, archives_leading_dir=False)
@serve_path_via_http
@with_tempfile
@known_failure_v6  # FIXME
@known_failure_direct_mode  #FIXME
def test_simple1(ind, topurl, outd):

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


@usecase  # created with
@with_tree(tree={
    '1.tar.gz': {
        'd': {"textfile": "1\n",
              "tooshort": "1"
              },
    "anothertext": "1 2 3"
    }
}, archives_leading_dir=False)
@serve_path_via_http
@with_tempfile
@known_failure_direct_mode  #FIXME
def test_crawl_autoaddtext(ind, topurl, outd):
    ds = create(outd, text_no_annex=True)
    with chpwd(outd):  # TODO -- dataset argument
        crawl_init(
            {'url': topurl, 'a_href_match_': '.*'}
            , save=True
            , template='simple_with_archives')
        crawl()
    ok_clean_git(outd)
    ok_file_under_git(outd, "anothertext", annexed=False)
    ok_file_under_git(outd, "d/textfile", annexed=False)
    ok_file_under_git(outd, "d/tooshort", annexed=True)


@with_tree(tree={
    'index.html': """<html><body>
    <a href="d1/">sub1</a>
    <a href="d2/">sub2</a>
</body></html>
""",
    'd1': {
        '1.dat': ''
    },
    'd2': {
        '2.dat': 'text'
}})
@serve_path_via_http
@with_tempfile
@known_failure_direct_mode  #FIXME
def test_recurse_follow(ind, topurl, outd):
    ds = create(outd, text_no_annex=True)
    def crawl_init_(**kw):
        return crawl_init(
            dict(url=topurl, a_href_match_='.*\.dat', fail_if_no_archives=False, **kw)
            , save=True
            , template='simple_with_archives'
            )

    with chpwd(outd):  # TODO -- dataset argument
        crawl_init_()
        # nothing is matched so it would  blow somehow
        with assert_raises(Exception):
            crawl()

        crawl_init_(a_href_follow='.*/d[1]/?')
        crawl()

    ok_clean_git(outd)
    ok_file_under_git(outd, "d1/1.dat", annexed=True)
    #ok_file_under_git(outd, "d/textfile", annexed=False)
    #ok_file_under_git(outd, "d/tooshort", annexed=True)

