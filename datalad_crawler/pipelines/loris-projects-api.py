# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling a LORIS API for projects endpoints"""

import json
import re
from os.path import basename, join

# Import necessary nodes
from datalad.utils import updated
from ..nodes.crawl_url import crawl_url
from ..nodes.annex import Annexificator
from datalad_crawler.consts import DATALAD_SPECIAL_REMOTE


# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.kaggle")


class ValidateArgs(object):
    """
    Class to perform some preliminary validation of the arguments provided to crawl-init.
    """

    def __init__(self, url=None, endpoints=None):
        self.url = url
        self.endpoints = endpoints

    def validate_args(self):
        """
        This function will validate that all arguments required are indeed present
        when running `datalad crawl-init --template loris-projects-api.py`

        :return: error message if the args provided do not pass the validation
         :rtype: str
        """
        cmd_example = "datalad crawl-init --template loris-projects-api.py" \
                       " url=<loris_base_url>/api/v0.0.3" \
                       " endpoints=projects/<project_name>/images,projects/<project_name>/candidates"

        if not self.url:
            return f"\n Please set url that LORIS API endpoints are relative to.\n" \
                   f" Example:  {cmd_example}\n"

        if not self.endpoints:
            return f"\n Please set a comma separated list of 'projects' API endpoints to crawl.\n" \
                   f" Example:  {cmd_example}\n"

    def validate_endpoints(self):
        """
        Validate that the list of endpoints provided matches a supported endpoint
        of loris-projects-api.py template.

        :return: error message that lists the supported endpoints
         :rtype: str
        """
        supported_endpoints = [
            'projects/<projectName>/images',
            'projects/<projectName>/bids',
            'projects/<projectName>/data_releases',
            'projects/<projectName>/recordings'
        ]
        supported_endpoints_pattern = re.compile(
            r'^projects/.+/((images/?)|(bids/?)|(data_releases/?)|(recordings/?)$)'
        )

        unsupported_endpoint_bool = False
        for endpoint in self.endpoints.split(','):
            if not re.match(supported_endpoints_pattern, endpoint):
                unsupported_endpoint_bool = True

        if unsupported_endpoint_bool:
            return f"\n The following endpoint(s) are not supported by this crawler.\n" \
                   f" List of supported endpoints: {', '.join(supported_endpoints)}\n"


class LorisProjectsAPIExtractor(object):
    """
    Class that extracts files from the LORIS API projects endpoints
    """

    def __init__(self, apibase=None, endpoints_list=None):
        self.apibase = apibase
        self.endpoints_list = endpoints_list

    def extract_project_images(self, data):
        """
        This function reads the JSON response of the LORIS API project images endpoint
        (<loris-url>/api/<api-version>/projects/<project-name>/images) to crawl.

        Note: there will be two different data organization depending on whether the
        file downloaded is a MINC file or a NIfTI file:
            - MINC files will be organized under `candidate/visit/images` folders
            - NIfTI files will be organized in a BIDS structure

        :param data: the JSON response of the queried API endpoint
         :type data: dict
        """
        response = json.loads(data['response'])

        for file_dict in response['Images']:
            candid   = file_dict['Candidate']
            visit    = file_dict['Visit']
            filename = basename(file_dict['Link'])

            if filename.endswith('.mnc'):
                # File organization of MINC files
                yield updated(data, {
                    "url" : join(self.apibase, 'candidates', candid),
                    "filename": "candidate.json",
                    "path": join("MINC_images", candid)
                })
                yield updated(data, {
                    "url" : join(self.apibase, 'candidates', candid, visit),
                    "filename": "visit.json",
                    "path": join("MINC_images", candid, visit)
                })
                yield updated(data, {
                    "url" : join(self.apibase, 'candidates', candid, visit, 'images'),
                    "path": join("MINC_images", candid, visit, 'images')
                })
                yield updated(data, {
                    "url" : self.apibase + file_dict["Link"],
                    "path": join("MINC_images", candid, visit, 'images')
                })
            elif filename.endswith(('.nii', '.nii.gz')):
                # TODO BIDS file organization
                # download NIfTI files in sub-<candid>/ses-<visit>/modality
                # download the sidecar JSON file attached in parameter_file
                bids_root_dir = 'BIDS_dataset'
                continue

            break  # TODO remove once done testing

    def extract_projects_data_releases(self, data):
        """
        This function reads the JSON response of the LORIS API project data_releases endpoint
        (<loris-url>/api/<api-version>/projects/<project-name>/data_releases) to crawl.

        :param data: the JSON response of the queried API endpoint
         :type data: dict
        """
        response = json.loads(data['response'])

        # determine the latest version of data release
        version = None
        files = []
        for release in response:
            current_version = release['Data_Release_Version']
            if not version:
                version = current_version
                files = release['Files']
            else:
                version = current_version if current_version > version else version
                files = release['Files']

        for file_dict in files:
            file_name = file_dict['File']
            file_link = file_dict['Link']
            yield updated(data, {
                "url"     : join(self.apibase, file_link),
                "filename": file_name,
                "path"    : join("non_imaging_data_releases", str(version))
            })
            break

    def extract_projects_bids(self, data):
        """
        This function reads the JSON response of the LORIS API project bids endpoint
        (<loris-url>/api/<api-version>/projects/<project-name>/bids) to crawl.

        :param data: the JSON response of the queried API endpoint
         :type data: dict
        """
        bids_root_dir = 'BIDS_dataset'
        response = json.loads(data['response'])

        for key in ['DatasetDescription', 'README', 'BidsValidatorConfig']:
            if key in response.keys():
                yield updated(data, {
                    'url' : self.apibase + response[key]['Link'],
                    'path': bids_root_dir
                })

        if 'Participants' in response.keys():
            yield updated(data, {
                'url' : self.apibase + response['Participants']['TsvLink'],
                'path': bids_root_dir
            })
            yield updated(data, {
                'url' : self.apibase + response['Participants']['JsonLink'],
                'path': bids_root_dir
            })

        if 'SessionFiles' in response.keys():
            for file_dict in response['SessionFiles']:
                candid = 'sub-' + file_dict['Candidate']
                visit = 'ses-' + file_dict['Visit']
                yield updated(data, {
                    'url' : self.apibase + file_dict['TsvLink'],
                    'path': join(bids_root_dir, candid, visit)
                })
                yield updated(data, {
                    'url' : self.apibase + file_dict['JsonLink'],
                    'path': join(bids_root_dir, candid, visit)
                })
                break  # TODO remove this once done testing

        if 'Images' in response.keys():
            for file_dict in response["Images"]:
                candid = 'sub-' + file_dict["Candidate"]
                visit = 'ses-' + file_dict["Visit"]
                subfolder = file_dict['Subfolder']
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
                break  # TODO remove this once done testing

    def extract_projects_recordings(self, data):
        """
        This function reads the JSON response of the LORIS API project recordings endpoint
        (<loris-url>/api/<api-version>/projects/<project-name>/recordings) to crawl.

        :param data: the JSON response of the queried API endpoint
         :type data: dict
        """
        response = json.loads(data['response'])

        bids_root_dir = 'BIDS_dataset'

        for file_dict in response['Recordings']:
            candid    = file_dict['Candidate']
            visit     = file_dict['Visit']
            modality  = file_dict['Modality']
            file_link = file_dict['Link']
            download_dir = join(bids_root_dir, candid, visit, modality)

            yield updated(data, {
                'url' : join(self.apibase, file_link),
                'path': download_dir
            })
            yield updated(data, {
                'url' : join(self.apibase, file_link, 'bidsfiles/channels'),
                'path': download_dir
            })
            yield updated(data, {
                'url' : join(self.apibase, file_link, 'bidsfiles/events'),
                'path': download_dir
             })
            yield updated(data, {
                'url' : join(self.apibase, file_link, 'bidsfiles/electrodes'),
                'path': download_dir
            })
            # yield updated(data, {
            #     'url' : join(self.apibase, file_link, 'bidsfiles/json'),
            #     'path': download_dir
            # })
            break  # TODO remove this once done testing


def pipeline(url=None, endpoints=None):
    """
    Pipeline to crawl/annex a LORIS database via the LORIS API.
    
    It will crawl every file matching the format of the $API/project/images/
    endpoint as documented in the LORIS API. Requires a LORIS version
    which has API v0.0.3-dev (or higher).
    """

    # Checks arguments provided to `datalad crawl-init`
    # (or stored in `.datalad/crawl/crawl.cfg` config file)
    arg_validation  = ValidateArgs(url, endpoints)
    invalid_message = arg_validation.validate_args()
    if invalid_message:
        raise RuntimeError(invalid_message)
    invalid_message = arg_validation.validate_endpoints()
    if invalid_message:
        raise RuntimeError(invalid_message)

    # Create the annex object
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
                    " and exclude=BIDS_dataset/dataset_description.json"
                    " and exclude=BIDS_dataset/participants.json"
                ]
    )

    # Initialize the LorisProjectsAPIExtractor class
    endpoints_list = endpoints.split(',')
    api_extractor  = LorisProjectsAPIExtractor(url, endpoints_list)

    urls_pipe = [crawl_url(url)]
    for endpoint in endpoints_list:
        endpoint_url = join(url, endpoint)
        lgr.info("Creating a pipeline to crawl data files from %s", join(url, endpoint))
        if re.match(r'^projects/.+/images/?$', endpoint):
            urls_pipe += [
                crawl_url(endpoint_url),
                api_extractor.extract_project_images,
                annex
            ]
        elif re.match(r'^projects/.+/recordings/?$', endpoint):
            urls_pipe += [
                crawl_url(endpoint_url),
                api_extractor.extract_projects_recordings,
                annex
            ]
        elif re.match(r'^projects/.+/data_releases/?$', endpoint):
            urls_pipe += [
                crawl_url(endpoint_url),
                api_extractor.extract_projects_data_releases,
                annex
            ]
        elif re.match(r'^projects/.+/bids/?$', endpoint):
            urls_pipe += [
                crawl_url(endpoint_url),
                api_extractor.extract_projects_bids,
                annex
            ]
        else:
            raise RuntimeError(f"\n{endpoint_url} is not supported by this crawler...\n")

    return [
        urls_pipe,
        annex.finalize()
    ]
