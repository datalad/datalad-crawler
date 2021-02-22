# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling BIDS exported files from a LORIS database"""

# Import necessary nodes
from ..nodes.crawl_url import crawl_url
from datalad.utils import updated
from ..nodes.annex import Annexificator
from datalad_crawler.consts import DATALAD_SPECIAL_REMOTE
from os.path import basename, join


import json
# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.kaggle")


class LorisAPIBIDSExtractor(object):

    def __init__(self, apibase=None, annex=None):
        self.apibase = apibase
        self.meta    = {}
        self.repo    = annex.repo

    def __call__(self, data):
        bids_root_dir = 'BIDS_dataset'
        jsdata = json.loads(data["response"])

        for key in ['DatasetDescription', 'README', 'BidsValidatorConfig']:
            if key in jsdata.keys():
                yield updated(data, {
                    'url' : self.apibase + jsdata[key]['Link'],
                    'path': bids_root_dir
                })

        if 'Participants' in jsdata.keys():
            yield updated(data, {
                'url' : self.apibase + jsdata['Participants']['TsvLink'],
                'path': bids_root_dir
            })
            yield updated(data, {
                'url' : self.apibase + jsdata['Participants']['JsonLink'],
                'path': bids_root_dir
            })

        if 'SessionFiles' in jsdata.keys():
            for file_dict in jsdata['SessionFiles']:
                candid   = 'sub-' + file_dict['Candidate']
                visit    = 'ses-' + file_dict['Visit']
                lgr.info(self.apibase + file_dict['JsonLink'])
                yield updated(data, {
                    'url' : self.apibase + file_dict['TsvLink'],
                    'path': join(bids_root_dir, candid, visit)
                })
                yield updated(data, {
                    'url' : self.apibase + file_dict['JsonLink'],
                    'path': join(bids_root_dir, candid, visit)
                })

        if 'Images' in jsdata.keys():
            for file_dict in jsdata["Images"]:
                candid    = 'sub-' + file_dict["Candidate"]
                visit     = 'ses-' + file_dict["Visit"]
                subfolder = file_dict['Subfolder']
                filename  = basename(file_dict["NiftiLink"])
                self.meta[filename] = file_dict
                yield updated(data, {
                    "url" : self.apibase + file_dict["NiftiLink"],
                    "path": join(bids_root_dir, candid, visit, subfolder)
                })
                for associated_file in ['JsonLink', 'BvalLink', 'BvecLink', 'EventLink']:
                    if associated_file in file_dict:
                        yield updated(data, {
                            "url" : self.apibase + file_dict[associated_file],
                            "path": join(bids_root_dir, candid, visit, subfolder)
                        })
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
                skip_problematic=True,
                special_remotes=[DATALAD_SPECIAL_REMOTE],
                options=[
                    "-c",
                    "annex.largefiles="
                    "exclude=README.md and exclude=DATS.json and exclude=logo.png"
                    " and exclude=.datalad/providers/loris.cfg"
                    " and exclude=.datalad/crawl/crawl.cfg"
                    " and exclude=*scans.json"
                    " and exclude=*bval"
                    " and exclude=dataset_description.json"
                    " and exclude=participants.json"
                ]
    )
    lorisapi = LorisAPIBIDSExtractor(apibase, annex)

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
