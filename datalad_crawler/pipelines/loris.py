# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling a LORIS database"""

# Import necessary nodes
from ..nodes.crawl_url import crawl_url
from datalad.utils import updated
from ..nodes.annex import Annexificator
from datalad_crawler.consts import DATALAD_SPECIAL_REMOTE
from os.path import basename


import json
# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.kaggle")


class LorisAPIExtractor(object):

    def __init__(self, apibase=None, annex=None):
        self.apibase = apibase
        self.meta    = {}
        self.repo    = annex.repo

    def __call__(self, data):
        jsdata = json.loads(data["response"])
        for candidate in jsdata["Images"]:
            filename = basename(candidate["Link"])
            self.meta[filename] = candidate
            yield updated(data, { "url" : self.apibase + candidate["Link"] })
        return

    def finalize(self):
        def _finalize(data):
            for filename in self.meta:
                metadata_setter = self.repo.set_metadata(
                    filename,
                    reset=self.meta[filename],
                )
                for meta in metadata_setter:
                    lgr.info("Appending metadata to %s", filename)
            yield data
        return _finalize


def pipeline(url=None, apibase=None):
    """Pipeline to crawl/annex a LORIS database via the LORIS API.
    
    It will crawl every file matching the format of the $API/project/images/
    endpoint as documented in the LORIS API. Requires a LORIS version
    which has API v0.0.3-dev (or higher).
    """
    if apibase is None:
        raise RuntimeError("Must set apibase that links are relative to.")

    lgr.info("Creating a pipeline to crawl data files from %s", url)
    annex = Annexificator(
                create=False,
                statusdb='json',
                special_remotes=[DATALAD_SPECIAL_REMOTE],
                options=[
                    "-c",
                    "annex.largefiles="
                    "exclude=Makefile and exclude=LICENSE* and exclude=ISSUES*"
                    " and exclude=CHANGES* and exclude=README*"
                    " and exclude=*.[mc] and exclude=dataset*.json"
                    " and exclude=*.txt"
                    " and exclude=*.tsv"
                ]
    )
    lorisapi = LorisAPIExtractor(apibase, annex)

    return [
        # Get the list of images
        [
            crawl_url(url),
            lorisapi,
            annex,
        ],
        annex.finalize(),
        lorisapi.finalize(),
    ]
