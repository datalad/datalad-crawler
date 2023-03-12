# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""A pipeline for crawling XNAT servers/datasets (e.g. NITRC/ir)"""

"""
Notes:

- xml entries for subject contain meta-data
- in longitudinal studies there could be multiple ages for a subject... find where
  it is
"""

import json
from ..nodes.misc import assign
from ..nodes.annex import Annexificator
from datalad.utils import updated

# Possibly instantiate a logger if you would like to log
# during pipeline creation
from logging import getLogger
lgr = getLogger("datalad.crawler.pipelines.xnat")

from datalad.tests.utils_pytest import eq_
from datalad.utils import assure_list, assure_bool


def list_to_dict(l, field):
    return {r.pop(field): r for r in l}


DEFAULT_RESULT_FIELDS = {'totalrecords', 'result'}
PROJECT_ACCESS_TYPES = {'public', 'protected', 'private'}


def lower_case_the_keys(d):
    """Create a dict with keys being lower cased but with a check against collisions
    
    If d is a list of tuple, would recurse into its elements
    """
    if not isinstance(d, dict):
        assert isinstance(d, (list, tuple))
        return d.__class__(
            lower_case_the_keys(x) for x in d
        )
    out = {}
    for k, v in d.items():
        kl = k.lower()
        if kl in out:
            raise ValueError(
                "We already got key %s=%r, but trying to add =%r"
                % (kl, out[kl], v)
            )
        out[kl] = v
    return out


def extract_subject_info(data):
    subject_item = data['items'][0]
    info = {'label': subject_item['data_fields']['label'], 
            'group': subject_item['data_fields'].get('group')}
    for child in subject_item['children']:
        if child['field'] == 'demographics':
            demographics = child['items'][0]['data_fields']
            info['gender'] = demographics.get('gender')
            info['age'] = demographics.get('age')
            info['handedness'] = demographics.get('handedness')
            break
    return info


def extract_experiment_info(data):
    experiment_item = data['items'][0]
    return experiment_item['data_fields']


class XNATServer(object):

    def __init__(self, topurl):
        self.topurl = topurl
        from datalad.downloaders.providers import Providers
        providers = Providers.from_config_files()
        self.downloader = providers.get_provider(topurl).get_downloader(topurl)
        # set without various methods
        self._experiment_labels = None

    @property
    def experiment_labels(self):
        if self._experiment_labels is None:
            lgr.debug("Experiment labels are not known yet")
            self.get_all_experiments()
        return self._experiment_labels

    def __call__(self, query,
                 format='json',
                 options=None,
                 return_plain=False,
                 fields_to_check=DEFAULT_RESULT_FIELDS):
        query_url = "%s/%s" % (self.topurl, query)
        options = options or {}
        if format:
            options['format'] = format
        if options:
            # TODO: use the helper we have
            query_url += "?" + '&'.join(("%s=%s" % (o, v) for o, v in options.items()))
        out = self.downloader.fetch(query_url)
        if format == 'json':
            j = json.loads(out)
            j = lower_case_the_keys(j)
            if return_plain:
                return j
            assert list(j) == ['resultset']

            jrs = lower_case_the_keys(j['resultset'])
            if fields_to_check:
                eq_(set(jrs.keys()), fields_to_check)
            return lower_case_the_keys(jrs['result'])
        return out

    def get_projects(self, limit=None, drop_empty=True, asdict=True):
        """Get list of projects 

        Parameters
        ----------
        limit: {'public', 'protected', 'private', None} or list of thereof
           'private' -- projects you have no any access to. 'protected' -- you could
           fetch description but not the data. None - would list all the projects

        drop_empty: bool
          whether to drop projects with no experiments.  Implies
          limit = 'public' since we need access to projects to determine if they
          are empty.  If drop_empty is set and limit is None, limit is set to
          'public'
        """

        limit = assure_list(limit)

        if drop_empty:
            # TODO: rework this logic/restriction
            #  yoh thinks this should not be implied (we could check "private"
            #  ones we have access to) here.
            if limit != ['public']:
                lgr.warning(
                    "Limit was set to %s but ATM we can drop_empty only if "
                    "limit is 'public'. Reset to 'public'",
                    repr(limit)
                )
            limit = ['public']


        kw = {}

        if limit:
            # Q yoh:  is this only for public? then check above should be
            #   if 'public' in limit, and assure_list(limit) should go above
            kw['options'] = {"accessible": "true"}
            kw['fields_to_check'] = DEFAULT_RESULT_FIELDS | {'title', 'xdat_user_id'}

        all_projects = self('data/projects', **kw)

        if limit:
            # double check that all the project_access thingies in the set which
            # we know
            assert all(p['project_access'] in PROJECT_ACCESS_TYPES
                       for p in all_projects)
            limited_projects = [
                p for p in all_projects
                if p['project_access'] in limit
            ]
        else:
            limited_projects = all_projects

        experiments = self.get_all_experiments()

        if drop_empty:
            # first pass: exclude projects without experiments
            non_empty_projects = set([ e['project'] for e in experiments ])
            out = []
            # second pass: descend into experiments to find files
            for p in limited_projects:
                if self.project_has_files(p['id']):
                    out.append(p)
                else:
                    lgr.debug("Skipping %s (no files)", p)
            lgr.info("Skipped %d empty projects", len(all_projects) - len(out))
        else:
            out = limited_projects

        return list_to_dict(out, 'id') if asdict else out

    def get_all_experiments(self):
        """Query XNAT server for all known experiments.

        Side effect: (re)assigns self._experiment_labels mapping which is also
        used for crawling an individual dataset

        Returns
        -------
        list of experiments
        """
        lgr.debug("Requesting full list of experiments")
        fields_to_check = DEFAULT_RESULT_FIELDS.union({'title'})
        experiments = self('data/experiments', fields_to_check=fields_to_check)
        self._experiment_labels = {e['id']: e['label'] for e in experiments}
        return experiments

    def project_has_files(self, project):
        for subject in self.get_subjects(project):
            for experiment in self.get_experiments(project, subject):
                if self.get_files(project, subject, experiment):
                    return True
        return False

    def get_subjects(self, project):
        return list_to_dict(
            self('data/projects/%(project)s/subjects' % locals()),
            'id'
        )

    def get_experiments(self, project, subject):
        fmt = 'data/projects/%(project)s/subjects/%(subject)s/experiments'
        url = fmt % locals()
        return list_to_dict(
            self(url, options={'xsiType': 'xnat:imageSessionData'}),
            'id'
        )

    def get_files(self, project, subject, experiment):
        files = []
        for rec_type in ('scans', 'assessors'):
            url = 'data/projects/%(project)s/subjects/%(subject)s/experiments/%(experiment)s/%(rec_type)s' % \
                      locals()
            recs = self(url)
            files_ = []
            for rec in recs:
                files_.extend(self(url + '/%(id)s/files' % rec, fields_to_check={'title', 'result', 'columns'}))
            for f in files_:
                f['rec_type'] = rec_type
            files.extend(files_)
        return files

    def get_all_files_for_project(self, project, subjects=None, experiments=None):
        # TODO: grow the dictionary with all the information about subject/experiment/file
        # to be yielded so we could tune up file name anyway we like
        for subject in (subjects or self.get_subjects(project)):
            subject_url = 'data/projects/%s/subjects/%s' % (project, subject)
            subject_data = self(subject_url, return_plain=True)
            subject_info = extract_subject_info(subject_data)
            for experiment in (experiments or self.get_experiments(project, subject)):
                experiment_data = self('data/experiments/%s' % experiment, 
                                       return_plain=True)
                experiment_info = extract_experiment_info(experiment_data)
                for file_ in self.get_files(project, subject, experiment):
                    file_info = updated(file_, {'subject_id': subject, 
                                                'subject_info': subject_info, 
                                                'experiment_id': experiment, 
                                                'experiment_info': experiment_info})
                    yield file_info


# define a pipeline factory function accepting necessary keyword arguments
# Should have no strictly positional arguments
def superdataset_pipeline(url, limit=None, drop_empty=True):
    """
    
    Parameters
    ----------
    url
    limit : TODO, optional
      Types of access to limit to, see XNAT.get_datasets
    drop_empty: bool, optional
      If set, do not create datasets which are empty (no files).
      Note - it requires obtaining details for every project, which could be
      a heavy operation
    kwargs

    Returns
    -------

    """

    annex = Annexificator(no_annex=True, allow_dirty=False)
    lgr.info("Creating a pipeline with url=%s limit=%s drop_empty=%s", url, limit, drop_empty)
    limit = assure_list(limit)
    drop_empty = assure_bool(drop_empty)

    def get_projects(data):
        xnat = XNATServer(url)
        for p in xnat.get_projects(
                asdict=False,
                limit=limit or PROJECT_ACCESS_TYPES,
                drop_empty=drop_empty
        ):
            yield updated(data, p)

    return [
        get_projects,
        assign({'project': '%(id)s',
                'dataset_name': '%(id)s',
                'url': url
                }, interpolate=True),
        # TODO: should we respect  x quarantine_status
        annex.initiate_dataset(
            template="xnat",
            data_fields=['project', 'url', 'project_access'],  # TODO: may be project_access
            # let's all specs and modifications reside in master
            # branch='incoming',  # there will be archives etc
            existing='skip'
            # further any additional options
        )
    ]


def pipeline(url, project, project_access='public', subjects=None):
    # TODO: Ben: Clarify parameters. In particular `project_access` is unclear to me
    subjects = assure_list(subjects)

    xnat = XNATServer(url)

    def get_project_info(data):
        out = xnat('data/projects/%s' % project,
                   return_plain=True
                   )
        # for NITRC I need to get more!
        # "http://nitrc_es.projects.nitrc.org/datalad/%s" % dataset
        items = out['items']
        assert len(items) == 1
        dataset_meta = items[0]['data_fields']
        # TODO: save into a file
        yield data

    def get_files(data):

        for f in xnat.get_all_files_for_project(project, subjects=subjects):
            # TODO: tune up filename
            # TODO: get url
            prefix = '/data/experiments/'
            assert f['uri'].startswith('%s' % prefix)
            # TODO:  use label for subject/experiment
            # TODO: might want to allow for
            #   XNAT2BIDS whenever that one is available:
            #     http://reproducibility.stanford.edu/accepted-projects-for-the-2nd-crn-coding-sprint/
            exp_label = xnat.experiment_labels[f['experiment_id']]
            yield updated(data,
                          {'url': url + f['uri'],
                           'path': f['uri'][len(prefix):], 
                           'name': '%s-%s' % (exp_label, f['name'])
                           })

    annex = Annexificator(
        create=False,  # must be already initialized etc
        # leave in Git only obvious descriptors and code snippets -- the rest goes to annex
        # so may be eventually we could take advantage of git tags for changing layout
        statusdb='json',
        special_remotes=['datalad'] if project_access != 'public' else None
    )

    return [
        get_project_info,
        [
            get_files,
            annex
        ],
        annex.finalize(cleanup=True, aggregate=True),
    ]
