# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling a LORIS database through the candidate API"""
import json
import os

# Import necessary nodes
from datalad.utils import updated
from ..nodes.crawl_url import crawl_url
from ..nodes.annex import Annexificator
from datalad_crawler.consts import DATALAD_SPECIAL_REMOTE

# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger

lgr = getLogger("datalad.crawler.pipelines.kaggle")


class add_url_suffix:
    def __init__(self, url_type, suffix):
        self.url_type = url_type
        self.suffix = suffix

    def __call__(self, data):
        yield updated(data, {self.url_type: data[self.url_type] + self.suffix})


class LorisCandidateAPI:
    def __init__(self, url):
        self.url = url

    def visits(self, data):
        response = json.loads(data["response"])
        for visit in response["Visits"]:
            yield updated(data, {"visit-url": self.url + "/" + visit})

    def images(self, data):
        response = json.loads(data["response"])
        for file_ in response["Files"]:
            filename = file_["Filename"]
            yield updated(data, {"url": data["visit-url"] + "/" + filename})

    def instruments(self, data):
        response = json.loads(data["response"])
        for instrument in response["Instruments"]:
            yield updated(data, {"instrument-url": data["visit-url"] + "/" + instrument})
    
    def instrument_data(self, data):
        if data == None:
            return
        else:
            response = json.loads(data["response"])
            meta = response["Meta"]
            filename = f"{meta['Candidate']}_{meta['Visit']}_{meta['Instrument']}"
            
            if os.path.lexists(f"instruments/{filename}"):
                os.unlink(f"instruments/{filename}")
            with open(f"instruments/{filename}", "w+") as f_out:
                os.chmod(f"instruments/{filename}", 0o775)
                json.dump(response[meta["Instrument"]], f_out)
                yield {"filename": filename}
         


def pipeline(url=None):
    """Pipeline to crawl/annex a LORIS database via the LORIS Candidate API.
    
    It will crawl every file matching the format of the $API/candidates/$candID/
    endpoint as documented in the LORIS API.
    """

    lgr.info("Creating a pipeline to crawl data files from %s", url)

    image_annex = Annexificator(
        path="images",
        create=True,
        statusdb="json",
        special_remotes=[DATALAD_SPECIAL_REMOTE],
        options=[
            "-c",
            "annex.largefiles="
            "exclude=Makefile and exclude=LICENSE* and exclude=ISSUES*"
            " and exclude=CHANGES* and exclude=README*"
            " and exclude=*.[mc] and exclude=dataset*.json"
            " and exclude=*.txt"
            " and exclude=*.tsv",
        ],
    ) 

    instrument_annex = Annexificator(
        path="instruments",
        create=True,
        statusdb="json",
        special_remotes=[DATALAD_SPECIAL_REMOTE],
        options=[
            "-c",
            "annex.largefiles="
            "exclude=Makefile and exclude=LICENSE* and exclude=ISSUES*"
            " and exclude=CHANGES* and exclude=README*"
            " and exclude=*.[mc] and exclude=dataset*.json"
            " and exclude=*.txt"
            " and exclude=*.tsv",
        ],
    )

    api = LorisCandidateAPI(url)

    return [
        [
            crawl_url(url),
            api.visits,
            [
                [
                    # Crawl candidate images
                    add_url_suffix("visit-url", "/images"),
                    crawl_url(input="visit-url"),
                    api.images,
                    image_annex,
                ],
                [
                    # Crawl candidate insturments
                    add_url_suffix("visit-url", "/instruments"),
                    crawl_url(input="visit-url"),
                    api.instruments,
                    crawl_url(input="instrument-url"),
                    api.instrument_data,
                    instrument_annex,
                ],
            ],
        ],
        image_annex.finalize(),
        instrument_annex.finalize()
    ]

