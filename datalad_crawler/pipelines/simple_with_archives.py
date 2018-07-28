# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling basic websites and annexing their content

It features:
- extraction of content from archives (see `a_href_match_` option)
- establishing 3-branch workflow with following branches:
  - incoming - where all content is downloaded as is
  - incoming-processed - where archives (if present) are extracted
    (automatically) based on the content of incoming branch
  - master - where incoming-processed is merged, so you could introduce
    your additions/changes/fixups to files so they would later be automatically
    merged with changes from the web which would propagate via
    incoming-processed branch
"""

# Import necessary nodes
from ..nodes.crawl_url import crawl_url
from ..nodes.misc import fix_url
from ..nodes.matches import (
    a_href_match,
    a_text_match,
)
from ..nodes.misc import find_files
from ..nodes.misc import sub
from ..nodes.annex import Annexificator
from datalad.utils import assure_bool
from datalad_crawler.consts import DATALAD_SPECIAL_REMOTE, ARCHIVES_SPECIAL_REMOTE
from datalad.support.strings import get_replacement_dict

# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.simple_with_archives")


def pipeline(url=None,
             # parameters for initial crawling
             a_href_match_='.*/download/.*\.(tgz|tar.*|zip)',
             a_href_follow=None,
             a_text_follow=None,
             rename=None,
             # how do we establish the path while crawling following the links
             path_buildup=None,  # 'relurl' - relative to initial url,  ?'a_text' - could construct from the "navigation bread crumbs"
             # working with tarballs:
             tarballs=None,  # deprecated
             fail_if_no_archives=True,
             add_archive_leading_dir=False,
             use_current_dir=False,
             leading_dirs_depth=1,
             archives_regex="\.(zip|tgz|tar(\..+)?)$",
             # heavy customizations so this could be used from other pipelines
             datalad_downloader=False,
             annex=None,
             add_annex_to_incoming_pipeline=False,
             incoming_pipeline=None,
             # Additional repo specs
             backend='MD5E'
):
    """Pipeline to crawl/annex a simple web page with some tarballs on it
    
    If .gitattributes file in the repository already provides largefiles
    setting, none would be provided here to calls to git-annex.  But if not -- 
    README* and LICENSE* files will be added to git, while the rest to annex

    Parameters
    ----------
    url : str
      Top URL to crawl
    a_href_match_: str, optional
      Regular expression for HTML A href option to match to signal which files
      to download
    a_href_follow: str, optional
      Regular expression for HTML A href option to follow/recurse into to look
      for more URLs
    a_text_follow: str, optional
      Regular expression for HTML A text content to follow/recurse into to look
      for more URLs
    tarballs: bool, optional
      old, use `fail_if_no_archives`
    fail_if_no_archives: bool, optional
      Fail if no archives were found
    archives_regex: str, optional
      Regular expression to define what files are archives and should be
      extracted
    path_buildup: (None, 'relpath')
      If not None, directs how to establish a path for the file out of url.
      `relpath` - relative to the initial url
    """

    if tarballs is not None:
        # compatibility
        fail_if_no_archives = tarballs
    # This is messy and non-uniform ATM :-/ TODO: use constraints etc for typing of options?
    fail_if_no_archives = assure_bool(fail_if_no_archives)

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

    if url:
        assert not incoming_pipeline

        follow_matchers = []
        if a_href_follow:
            follow_matchers.append(a_href_match(a_href_follow))
        if a_text_follow:
            follow_matchers.append(a_text_match(a_text_follow))

        crawler = crawl_url(url, matchers=follow_matchers)

        from datalad_crawler.nodes.misc import debug
        incoming_pipeline = [ # Download all the archives found on the project page
            crawler,
            a_href_match(a_href_match_, min_count=1, finalize_each=False),
            debug(fix_url),
        ]
        if path_buildup == 'relpath':
            incoming_pipeline += [

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
                find_files(archives_regex, fail_if_none=fail_if_no_archives),  # So we fail if none found -- there must be some! ;)),
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
