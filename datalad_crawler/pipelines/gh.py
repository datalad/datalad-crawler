# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling an arbitrary GitHub organization"""

# I guess due to all the "import magic" we can't simply force load of
# global  github module whenever there is a local one, so we will rename
# local one

import re

from datalad.api import Dataset, install
from datalad.support import path as op
from datalad.downloaders.credentials import UserPassword

# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.github")


def pipeline(org=None, repo_type='sources', include='.*', exclude='--'):
    """Crawl github organization and install all matching repos as subdatasets

    Parameters
    ----------
    org: str
      GitHub Organization
    repo_type: ('all', 'public', 'private', 'forks', 'sources', 'member'), optional
      Type of the repositories to consider. Passed to github's module .get_repo.
    include: str, optional
      (search) regex to define which repositories to consider
    exclude: str, optional
      (search) regex to define which of the considered repositories to exclude.
      By default we exclude all repositories with '--' in the name which we
      assume defines the dataset boundary, so for `ds1--subds2` there should
      also be `ds` repository which would define the relationship to `subds2`

    Returns
    -------
    list:
      pipeline
    """
    assert org, "Organization must be provided"
    import github as gh
    # TODO: consider elevating that function to a "public" helper
    from datalad.distribution.create_sibling_github import _get_github_entity
    superds = Dataset('.')
    def crawl_github_org(data):
        assert list(data) == ['datalad_stats'], data
        cred = UserPassword('github')
        entity = _get_github_entity(gh, cred, None, None, org)
        all_repos = list(entity.get_repos(repo_type))

        for repo in all_repos:
            name = repo.name
            if include and not re.search(include, name):
                lgr.debug(
                    "Skipping %s since include regex search returns nothing", repo
                )
                continue
            if exclude and not re.search(exclude, name):
                lgr.debug(
                    "Skipping %s since exclude regex search returns smth", repo
                )
                continue
            # Let's just do everything here
            dspath = name
            if op.exists(dspath):
                lgr.info("Skipping %s since already exists", name)
                # although we could just do install, which would at least
                # verify that url is the same
            # TODO: all the recursive etc options
            ds = superds.install(dspath, source=repo.clone_url)
            # if anyone down the line needs it
            yield {
                'dataset': ds,
                'dataset_path': dspath,
                'dataset_name': name,
                'dataset_url': repo.clone_url,
            }

    # annex = Annexificator(no_annex=True, allow_dirty=True)
    lgr.info("Creating a pipeline for github organization %s", org)
    return [
        crawl_github_org,
        # annex.initiate_dataset(
        #     # We must not modify them
        #     # template="GitHub",  # TODO: should be git - nothing githubish there AFAIK
        #     data_fields=['dataset'],
        #     existing='skip'
        # )
    ]


# # There is nothing github'ish in it
# and actually no reason for some pipeline for now
# # We assume that repo already cloned, so "crawling" would only consists of
# # call to update
# def pipeline(merge=True, recursive=False, reobtain_data=False):
#     recursive = assure_bool(recursive)
#     merge = assure_bool(merge)
#     reobtain_data = assure_bool(reobtain_data)
#
#     def _update(data):
#         assert not data  # nothing is expected
#         for r in update(merge=merge, recursive=recursive, reobtain_data=reobtain_data):
#             yield updated(data, {'update_result': r})
#
#     return [
#         _update
#     ]