# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling a crcns dataset"""

from ..consts import DATALAD_SPECIAL_REMOTE, ARCHIVES_SPECIAL_REMOTE
from ..utils import flatten
# Import necessary nodes
from ..nodes.crawl_url import crawl_url
from ..nodes.misc import fix_url
from ..nodes.matches import a_href_match
from ..nodes.misc import find_files
from ..nodes.misc import sub
from ..nodes.annex import Annexificator
from datalad.support.strings import get_replacement_dict

# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.simple_with_archives")


def pipeline(url=None,
             a_href_match_=r'.*/download/.*\.(tgz|tar.*|zip|gz)',
             tarballs=True,
             datalad_downloader=False,
             use_current_dir=False,
             leading_dirs_depth=1,
             rename=None,
             backend='MD5E',
             add_archive_leading_dir=False,
             archives_re=r"\.(zip|tgz|tar(\..+)?)$",
             annex=None,
             add_annex_to_incoming_pipeline=False,
             incoming_pipeline=None):
    """Pipeline to crawl/annex a simple web page with some tarballs on it
    
    If .gitattributes file in the repository already provides largefiles
    setting, none would be provided here to calls to git-annex.  But if not -- 
    README* and LICENSE* files will be added to git, while the rest to annex
    """

    if not isinstance(leading_dirs_depth, int):
        leading_dirs_depth = int(leading_dirs_depth)

    lgr.info("Creating a pipeline to crawl data files from %s", url)
    if annex is None:
        # if no annex to use was provided -- let's just make one
        special_remotes = []
        if tarballs:
            special_remotes.append(ARCHIVES_SPECIAL_REMOTE)
        if datalad_downloader:
            special_remotes.append(DATALAD_SPECIAL_REMOTE)
        annex = Annexificator(
            create=False,  # must be already initialized etc
            backend=backend,
            statusdb='json',
            special_remotes=special_remotes,
            largefiles="exclude=README* and exclude=LICENSE*"
        )
        if incoming_pipeline:
            # if incoming pipeline already has an Annexificator, it could cause
            # weird or incorrect behavior unless it was somehow VERY intentional
            # So we will check and issue a warning if any node is an Annexificator
            annexificators = [
                n for n in flatten(incoming_pipeline)
                if isinstance(n, Annexificator)
            ]
            if annexificators:
                lgr.warning(
                    "incoming_pipeline already contains annexificator(s): %s. "
                    "Most likely you intended to provide annex= option into "
                    "this pipeline with the used in incoming_pipeline Annexificator. "
                    "Otherwise things might not work as intended",
                    ', '.join(map(repr, annexificators))
                )

    if url:
        assert not incoming_pipeline
        crawler = crawl_url(url)
        incoming_pipeline = [ # Download all the archives found on the project page
            crawler,
            a_href_match(a_href_match_, min_count=1),
            fix_url,
        ]
        if rename:
            incoming_pipeline += [sub({'filename': get_replacement_dict(rename)})]
        incoming_pipeline += [annex]
    else:
        # no URL -- nothing to crawl -- but then should have been provided
        assert incoming_pipeline
        if add_annex_to_incoming_pipeline:
            incoming_pipeline.append(annex)


    # TODO: we could just extract archives processing setup into a separate pipeline template
    return [
        annex.switch_branch('incoming', parent='master'),
        [
            incoming_pipeline,
        ],
        annex.switch_branch('incoming-processed'),
        [   # nested pipeline so we could skip it entirely if nothing new to be merged
            annex.merge_branch('incoming', strategy='theirs', commit=False),  #, skip_no_changes=False),
            [   # Pipeline to augment content of the incoming and commit it to master
                find_files(archives_re, fail_if_none=tarballs),  # So we fail if none found -- there must be some! ;)),
                annex.add_archive_content(
                    existing='archive-suffix',
                    # Since inconsistent and seems in many cases no leading dirs to strip, keep them as provided
                    strip_leading_dirs=bool(leading_dirs_depth),
                    delete=True,
                    leading_dirs_depth=leading_dirs_depth,
                    use_current_dir=use_current_dir,
                    rename=rename,
                    exclude='.*__MACOSX.*',  # some junk penetrates
                    add_archive_leading_dir=add_archive_leading_dir
                ),
            ],
        ],
        annex.switch_branch('master'),
        annex.merge_branch('incoming-processed', allow_unrelated=True),
        annex.finalize(cleanup=True),
    ]
