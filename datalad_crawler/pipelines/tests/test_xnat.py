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
from os.path import join as opj
from os.path import exists
from mock import patch
from functools import wraps

from ...nodes.crawl_url import crawl_url
from ...nodes.matches import *
from ...pipeline import run_pipeline, FinishPipeline

from ...nodes.misc import Sink, assign, range_node, interrupt_if
from ...nodes.annex import Annexificator, initiate_dataset
from ...pipeline import load_pipeline_from_module

from datalad.support.stats import ActivityStats
from datalad.support.gitrepo import GitRepo
from datalad.support.annexrepo import AnnexRepo

from datalad.api import clean
from datalad.utils import chpwd
from datalad.utils import find_files
from datalad.utils import swallow_logs
from datalad.tests.utils_pytest import with_tree
from datalad.tests.utils_pytest import eq_, assert_not_equal, ok_, ok_startswith
from datalad.tests.utils_pytest import assert_in, assert_is_generator
from datalad.tests.utils_pytest import skip_if_no_module
from datalad.tests.utils_pytest import with_tempfile
from datalad.tests.utils_pytest import serve_path_via_http
from datalad.tests.utils_pytest import skip_if_no_network
from datalad.tests.utils_pytest import use_cassette
from datalad.tests.utils_pytest import ok_file_has_content
from datalad.tests.utils_pytest import ok_file_under_git
from datalad.downloaders.tests.utils import get_test_providers

import pytest

import logging
from logging import getLogger
lgr = getLogger('datalad.crawl.tests')


#
# Some helpers
#

from ..xnat import XNATServer
from ..xnat import PROJECT_ACCESS_TYPES
from ..xnat import superdataset_pipeline
from ..xnat import pipeline
from datalad.tests.utils_pytest import skip_if_no_network

NITRC_IR = 'https://www.nitrc.org/ir'
CENTRAL_XNAT = 'https://central.xnat.org'


def skip_xnat(func):
    """Skips test unless DATALAD_TEST_XNAT is set"""
    @wraps(func)
    def newfunc(*args, **kwargs):
        skip_if_no_network()
        if not os.getenv('DATALAD_TEST_XNAT'):
            pytest.skip('Run this test by setting DATALAD_TEST_XNAT')
        return func(*args, **kwargs)
    return newfunc


@skip_xnat
@pytest.mark.parametrize("url,project,empty_project,subjects", [
    (NITRC_IR, 'fcon_1000', None, ['xnat_S00401', 'xnat_S00447']),
    (CENTRAL_XNAT, 'CENTRAL_OASIS_LONG', 'ADHD200', ['OAS2_0001', 'OAS2_0176']),
])
@use_cassette('test_basic_xnat_interface')
def test_basic_xnat_interface(url, project, empty_project, subjects):
    nitrc = XNATServer(url)
    projects = nitrc.get_projects()
    # verify that we still have projects we want!
    assert_in(project, projects)
    if empty_project:
        all_projects = nitrc.get_projects(drop_empty=False)
        assert len(all_projects) > len(projects)
        assert empty_project in all_projects
        assert empty_project not in projects
    projects_public = nitrc.get_projects(limit='public')
    import json
    print(json.dumps(projects_public, indent=2))
    assert len(projects_public) <= len(projects)
    assert not set(projects_public).difference(projects)
    eq_(set(projects),
        set(nitrc.get_projects(limit=PROJECT_ACCESS_TYPES)))

    subjects_ = nitrc.get_subjects(project)
    assert len(subjects_)
    experiments = nitrc.get_experiments(project, subjects[0])
    # NOTE: assumption that there is only one experiment
    files1 = nitrc.get_files(project, subjects[0], experiments.keys()[0])
    assert files1

    experiments = nitrc.get_experiments(project, subjects[1])
    files2 = nitrc.get_files(project, subjects[1], experiments.keys()[0])
    assert files2

    ok_startswith(files1[0]['uri'], '/data')
    gen = nitrc.get_all_files_for_project(project,
                                          subjects=subjects,
                                          experiments=[experiments.keys()[0]])
    assert_is_generator(gen)
    all_files = list(gen)
    if len(experiments) == 1:
        eq_(len(all_files), len(files1) + len(files2))
    else:
        # there should be more files due to multiple experiments which we didn't actually check
        assert len(all_files) > len(files1) + len(files2)

@skip_xnat
@with_tempfile(mkdir=True)
def test_smoke_pipelines(d=None):
    # Just to verify that we can correctly establish the pipelines
    AnnexRepo(d, create=True)
    with chpwd(d):
        with swallow_logs():
            for p in [superdataset_pipeline(NITRC_IR)]:
                print(p)
                ok_(len(p) > 1)


@skip_xnat
@with_tempfile(mkdir=True)
def test_nitrc_superpipeline(outd=None):
    with chpwd(outd):
        pipeline = superdataset_pipeline(NITRC_IR)
        out = run_pipeline(pipeline)
    eq_(len(out), 1)
    # TODO: actual tests on what stuff was crawled


test_nitrc_superpipeline.tags = ['integration']


@skip_xnat
@with_tempfile
def test_nitrc_pipeline(outd=None):
    get_test_providers('https://www.nitrc.org/ir/')
    from datalad.distribution.dataset import Dataset
    ds = Dataset(outd).create()
    with chpwd(outd):
        out = run_pipeline(
            pipeline(NITRC_IR, project='fcon_1000', subjects=['xnat_S00401'])
        )
    eq_(len(out), 1)


test_nitrc_superpipeline.tags = ['integration']
