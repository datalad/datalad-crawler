# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##

from datalad_crawler.pipelines.tests.test_utils import _test_smoke_pipelines
from ..balsa import pipeline as ofpipeline, superdataset_pipeline
import os
import logging
from os.path import exists
from glob import glob
from os.path import join as opj
from mock import patch

from ...nodes.crawl_url import crawl_url
from ...nodes.matches import *
from ...pipeline import run_pipeline, FinishPipeline

from ...nodes.misc import Sink, assign, range_node, interrupt_if
from ...nodes.annex import Annexificator, initiate_dataset
from ...pipeline import load_pipeline_from_module

from datalad.support.stats import ActivityStats
from datalad.support.gitrepo import GitRepo
from datalad.support.annexrepo import AnnexRepo

from datalad.utils import chpwd
from datalad.utils import find_files
from datalad.utils import swallow_logs
from datalad.tests.utils_pytest import with_tree
from datalad.tests.utils_pytest import eq_, assert_not_equal, ok_, assert_raises
from datalad.tests.utils_pytest import assert_in, assert_not_in, assert_true
from datalad.tests.utils_pytest import skip_if_no_module
from datalad.tests.utils_pytest import with_tempfile
from datalad.tests.utils_pytest import serve_path_via_http
from datalad.tests.utils_pytest import skip_if_no_network
from datalad.tests.utils_pytest import use_cassette
from datalad.tests.utils_pytest import ok_file_has_content
from datalad.tests.utils_pytest import ok_file_under_git

from logging import getLogger
lgr = getLogger('datalad.crawl.tests')


def test_smoke_pipelines():
    _test_smoke_pipelines(superdataset_pipeline, [])


TEST_TREE1 = {
    'study': {
        'show': {
            'WG33': {
                'index.html': """<html><body>
                                    <div>
                                        <a href="/study/download/WG33.tar.gz">Download (146 MB)</a>
                                        <a href="/file/show/JX5V">file1.nii</a>
                                        <a href="/file/show/R1BX">dir1 / file2.nii</a>
                                    </div>
                                    <div>
                                        <p>
                                            <span class="attributeLabel">SPECIES:</span><br>
                                            Human
                                        </p>
                                        <p>
                                            <span class="attributeLabel">DESCRIPTION:</span><br>
                                            DC Van Essen, J Smith, MF Glasser (2016) PMID: 27074495
                                        </p>
                                        <p>
                                            <span class="attributeLabel">PUBLICATION:</span><br>
                                            <span>NeuroImage</span>
                                        </p>
                                    </div>
                                    <div>
                                        <span class="attributeLabel">AUTHORS:</span><br>
                                        <ul>
                                            <li>DC Van Essen</li>
                                            <li>J Smith</li>
                                            <li>MF Glasser</>
                                        </ul>
                                    </div>
                                  </body></html>"""
            },
        },
        'download': {
            'WG33.tar.gz': {
                    'file1.nii': "content of file1.nii",
                    'dir1': {
                        'file2.nii': "content of file2.nii",
                    }
            }
        }
    },
    'file': {
        'show': {
            'JX5V': {
                'index.html': """<html><body>
                                    <a href="/file/download/file1.nii">Download (120 MB)</a>
                                </body></html>"""
            },
            'R1BX': {
                'index.html': """<html><body>
                    <a href="/file/download/dir1/file2.nii">Download (26 MB)</a>
                </body></html>"""
            }

        },

        'download': {
            'file1.nii': "content of file1.nii",
            'dir1': {
                'file2.nii': "content of file2.nii",
            }
        }
    },

}

@with_tree(tree=TEST_TREE1, archives_leading_dir=False)
@serve_path_via_http
@with_tempfile
@with_tempfile
def test_balsa_extract_meta(ind=None, topurl=None, outd=None, clonedir=None):
    list(initiate_dataset(
        template="balsa",
        dataset_name='dataladtest-WG33',
        path=outd,
        data_fields=['dataset_id'])({'dataset_id': 'WG33'}))

    with chpwd(outd):
        pipeline = ofpipeline('WG33', url=topurl)
        out = run_pipeline(pipeline)
    eq_(len(out), 1)

    with chpwd(outd):
        assert_true(exists(".datalad/meta/balsa.json"))
        f = open(".datalad/meta/balsa.json", 'r')
        contents = f.read()
    assert_true("SPECIES" and "DESCRIPTION" and "PUBLICATION" and "AUTHORS" in contents)


_PLUG_HERE = '<!-- PLUG HERE -->'


@with_tree(tree={

    'study': {
        'show': {
            'WG33': {
                'index.html': """<html><body>
                                    <a href="/study/download/WG33.tar.gz">Download (146 MB)</a>
                                    <a href="/file/show/JX5V">file1.nii</a>
                                    <a href="/file/show/R1BX">dir1 / file2.nii</a>
                                    %s
                                  </body></html>""" % _PLUG_HERE,
            },
        },
        'download': {
            'WG33.tar.gz': {
                    'file1.nii': "content of file1.nii",
                    'dir1': {
                        'file2.nii': "content of file2.nii",
                    }
            }
        }
    },

    'file': {
        'show': {
            'JX5V': {
                'index.html': """<html><body>
                                    <a href="/file/download/file1.nii">Download (120 MB)</a>
                                </body></html>"""
            },
            'R1BX': {
                'index.html': """<html><body>
                    <a href="/file/download/dir1/file2.nii">Download (26 MB)</a>
                </body></html>"""
            }

        },

        'download': {
            'file1.nii': "content of file1.nii",
            'dir1': {
                'file2.nii': "content of file2.nii",
                }
            }
        },
    },
    archives_leading_dir=False
)
@serve_path_via_http
@with_tempfile
@with_tempfile
def test_balsa_pipeline1(ind=None, topurl=None, outd=None, clonedir=None):
    list(initiate_dataset(
        template="balsa",
        dataset_name='dataladtest-WG33',
        path=outd,
        data_fields=['dataset_id'])({'dataset_id': 'WG33'}))

    with chpwd(outd):
        pipeline = ofpipeline('WG33', url=topurl)
        out = run_pipeline(pipeline)
    eq_(len(out), 1)

    repo = AnnexRepo(outd, create=False)  # to be used in the checks
    # Inspect the tree -- that we have all the branches
    branches = {'master', 'incoming', 'incoming-processed', 'git-annex'}
    eq_(set(repo.get_branches()), branches)
    # since now we base incoming on master -- and there were nothing custom
    # in master after incoming-processed, both branches should be the same
    eq_(repo.get_hexsha('master'), repo.get_hexsha('incoming-processed'))
    # but that one is different from incoming
    assert_not_equal(repo.get_hexsha('incoming'), repo.get_hexsha('incoming-processed'))

    get_branch_commits = repo.get_branch_commits_ \
        if hasattr(repo, 'get_branch_commits_') else repo.get_branch_commits
    commits = {b: list(get_branch_commits(b)) for b in branches}
    # all commits out there -- init ds + init crawler + 1*(incoming, processed)
    # The number of commits in master differs based on the create variant used
    # (the one DataLad's master makes only one commit).
    ncommits_master = len(commits["master"])
    assert_in(ncommits_master, [4, 5])
    # incoming branches from master but lacks one merge commit.
    eq_(len(commits['incoming']), ncommits_master - 1)
    # incoming-processed is on master.
    eq_(len(commits['incoming-processed']), ncommits_master)

    with chpwd(outd):
        eq_(set(glob('*')), {'dir1', 'file1.nii'})
        all_files = sorted(find_files('.'))

    fpath = opj(outd, 'file1.nii')
    ok_file_has_content(fpath, "content of file1.nii")
    ok_file_under_git(fpath, annexed=True)
    fpath2 = opj(outd, 'dir1', 'file2.nii')
    ok_file_has_content(fpath2, "content of file2.nii")
    ok_file_under_git(fpath2, annexed=True)

    target_files = {
        './.datalad/crawl/crawl.cfg',
        './.datalad/crawl/statuses/incoming.json',
        './.datalad/meta/balsa.json',
        './.datalad/config',
        './file1.nii', './dir1/file2.nii',
    }

    eq_(set(all_files), target_files)


# this test should raise warning that canonical tarball does not have one of the files listed
# and that a listed file differs in content
_PLUG_HERE = '<!-- PLUG HERE -->'


@with_tree(tree={
    'study': {
        'show': {
            'WG33': {
                'index.html': """<html><body>
                                    <a href="/study/download/WG33.tar.gz">Download (172 MB)</a>
                                    <a href="/file/show/JX5V">file1.nii</a>
                                    <a href="/file/show/RIBX">dir1 / file2.nii</a>
                                    <a href="/file/show/GSRD">file1b.nii</a>
                                    %s
                                  </body></html>""" % _PLUG_HERE,
            },
        },
        'download': {
            'WG33.tar.gz': {
                'file1.nii': "content of file1.nii",
                'dir1': {
                    'file2.nii': "content of file2.nii",
                }
            }
        }
    },
    'file': {
        'show': {
            'JX5V': {
                'index.html': """<html><body>
                                    <a href="/file/download/file1.nii">Download (120 MB)</a>
                                </body></html>"""
            },
            'R1BX': {
                'index.html': """<html><body>
                    <a href="/file/download/dir1/file2.nii">Download (26 MB)</a>
                </body></html>"""
            },
            'GSRD': {
                'index.html': """<html><body>
                    <a href="/file/download/file1b.nii">Download (26 MB)</a>
                 </body></html>"""
            }

        },
        'download': {
            'file1.nii': "content of file1.nii is different",
            'file1b.nii': "content of file1b.nii",
            'dir1': {
                'file2.nii': "content of file2.nii",
                }
            }
        },
    },
    archives_leading_dir=False
)
@serve_path_via_http
@with_tempfile
@with_tempfile
def test_balsa_pipeline2(ind=None, topurl=None, outd=None, clonedir=None):
    list(initiate_dataset(
        template="balsa",
        dataset_name='dataladtest-WG33',
        path=outd,
        data_fields=['dataset_id'])({'dataset_id': 'WG33'}))

    with chpwd(outd):
        with swallow_logs(new_level=logging.WARN) as cml:
            pipeline = ofpipeline('WG33', url=topurl)
            out = run_pipeline(pipeline)
            assert_true('The following files do not exist in the canonical tarball, '
                        'but are individually listed files and will not be kept:'
                        in cml.out)
            assert_true('./file1.nii varies in content from the individually downloaded '
                        'file with the same name, it is removed and file from canonical '
                        'tarball is kept' in cml.out)
    eq_(len(out), 1)

    with chpwd(outd):
        eq_(set(glob('*')), {'dir1', 'file1.nii'})
        all_files = sorted(find_files('.'))

    fpath = opj(outd, 'file1.nii')
    ok_file_has_content(fpath, "content of file1.nii")
    ok_file_under_git(fpath, annexed=True)
    fpath2 = opj(outd, 'dir1', 'file2.nii')
    ok_file_has_content(fpath2, "content of file2.nii")
    ok_file_under_git(fpath2, annexed=True)

    target_files = {
        './.datalad/config',
        './.datalad/crawl/crawl.cfg',
        './.datalad/crawl/statuses/incoming.json',
        './.datalad/meta/balsa.json',
        './file1.nii',
        './dir1/file2.nii',
    }

    eq_(set(all_files), target_files)
