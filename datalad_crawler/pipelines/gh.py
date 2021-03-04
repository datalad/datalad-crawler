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
from datalad.support.gitrepo import GitRepo
from datalad.utils import (
    assure_bool,
    assure_list_from_str,
    rmtree,
    updated
)
from datalad.downloaders.credentials import UserPassword

# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.github")


def pipeline(org=None,
             repo_type='sources', include='.*', exclude=None,
             metadata_nativetypes=None, aggregate=False,
             get_data=False, drop_data=False):
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
    metadata_nativetypes: list, optional
      List of metadata native types to define (locally within .git/config to
      not change repository itself) for metadata aggregation
    aggregate: bool, optional
      Aggregate metadata after crawling a new dataset
    get_data: bool, optional
      Get data for a new dataset
    drop_data: bool, optional
      Drop data for a new dataset after being done

    Returns
    -------
    list:
      pipeline
    """
    assert org, "Organization must be provided"
    aggregate = assure_bool(aggregate)
    get_data = assure_bool(get_data)
    drop_data = assure_bool(drop_data)

    import github as gh
    # TODO: consider elevating that function to a "public" helper
    from datalad.support.github_ import _gen_github_entity
    superds = Dataset('.')
    if metadata_nativetypes:
        metadata_nativetypes = assure_list_from_str(metadata_nativetypes, sep=',')

    aggregate_later = []
    def crawl_github_org(data):
        assert list(data) == ['datalad_stats'], data
        # TODO: actually populate the datalad_stats with # of datasets and
        # possibly amount of data downloaded in get below
        # Needs DataLad >= 0.13.6~7^2~3 where password was removed
        entity, cred = next(_gen_github_entity(None, org))
        all_repos = list(entity.get_repos(repo_type))

        for repo in all_repos:
            name = repo.name
            if include and not re.search(include, name):
                lgr.debug(
                    "Skipping %s since include regex search returns nothing", name
                )
                continue
            if exclude and re.search(exclude, name):
                lgr.debug(
                    "Skipping %s since exclude regex search returns smth", name
                )
                continue
            # Let's just do everything here
            dspath = name
            if op.exists(dspath):
                lgr.info("Skipping %s since already exists", name)
                # although we could just do install, which would at least
                # verify that url is the same... to not try to aggregate
                # etc, we will just skip for now
                continue

            # TODO: all the recursive etc options
            try:
                ds = superds.install(
                    dspath, source=repo.clone_url, get_data=get_data,
                    on_failure='continue'
                )
            except Exception as exc:
                if all(f.get('action', '') == 'add_submodule' and f.get('status', '') == 'error' for f in exc.failed):
                    # since we do not like nice exceptions and want to parse arbitrary text
                    # in the return records... let's resist that urge and redo the check
                    # since if no commit -- likely reason is an empty repo
                    if GitRepo(dspath).get_hexsha() is None:
                        lgr.warning(
                            "Cloned an empty repository.  Removing and proceeding without error"
                        )
                        rmtree(dspath)
                        continue
                if all(f.get('action', '') == 'get' for f in exc.failed):
                    lgr.warning(
                        "We failed to obtain %d files, extracted metadata etc might be incomplete",
                        len(exc.failed)
                    )
                    ds = Dataset(exc.failed[0]['refds'])
                else:
                    raise

            if metadata_nativetypes:
                lgr.info("Setting native metadata types to include %s",
                         ", ".join(metadata_nativetypes))
                nativetypes = ds.config.obtain('datalad.metadata.nativetype',
                                               default=[])
                for nativetype in metadata_nativetypes:
                    if nativetype not in nativetypes:
                        lgr.debug("Adding %s nativetype", nativetype)
                        ds.config.add('datalad.metadata.nativetype', nativetype, where='local')
                    else:
                        lgr.debug("Not adding %s nativetype since already defined", nativetype)
            # if anyone down the line needs it
            aggregate_later.append(dspath)
            yield {
                'dataset': ds,
                'superdataset': superds,
                'dataset_path': dspath,
                'dataset_name': name,
                'dataset_url': repo.clone_url,
            }


    def do_aggregate_metadata(data):
        # For now just aggregate into superdataset, and assume it is always provided!
        agg_out = data['superdataset'].aggregate_metadata(
            data['dataset_path'],
            recursive=True,  # I feel greedy
            incremental=True,
            update_mode='target'  # we aggregate into superdataset!
        )
        yield dict(data, aggregate_metadata_result=agg_out)

    def do_drop_data(data):
        lgr.info("Dropping all data for %(dataset)s", data)
        # This should fail to drop annexed metadata since no copies
        # would be known
        # Actually - no, since we aggregate only into its super!
        ds = data['dataset']
        drop_res = ds.drop('.')
        # notTODO: annex forget -- since initial crawl, should be perfectly
        # fine and might be of assistance to reduce impact on .git size
        # Nope -- we do not want to mess with original openneuro's git-annex
        # history.
        ds.repo.gc(allow_background=False)
        yield dict(data, drop_result=drop_res)

    def do_superds_aggregate_metadata(data):
        # nothing in data would be of use, and we know superds
        yield dict(
            data,
            aggregate_metadata_super_result=superds.aggregate_metadata(
                '.',
                incremental=True,
            )
        )

    # annex = Annexificator(no_annex=True, allow_dirty=True)
    lgr.info("Creating a pipeline for github organization %s", org)
    pipeline = [
            crawl_github_org,
    ]

    if aggregate:
        pipeline.append(do_aggregate_metadata)

    if drop_data:
        pipeline.append(do_drop_data)

    if aggregate:
        # but also we need a final aggregate for super ds itself
        pipeline = [
            pipeline,
            do_superds_aggregate_metadata
        ]

    return pipeline


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
