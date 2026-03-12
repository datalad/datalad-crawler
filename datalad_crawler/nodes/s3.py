# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Basic crawler for the web
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from datalad.utils import updated
from datalad.dochelpers import exc_str
from datalad.downloaders.providers import Providers
from datalad.downloaders.s3 import S3Downloader
from datalad.support.exceptions import TargetFileAbsent
from datalad.support.network import urlquote
from datalad.support.status import FileStatus
from ..dbs.versions import SingleVersionDB

from logging import getLogger
lgr = getLogger('datalad.crawl.s3')

# Sentinel for sorting entries that lack LastModified (e.g. prefixes)
_MIN_DATETIME = datetime.min.replace(tzinfo=timezone.utc)


def _list_bucket(
    client: Any,
    bucket_name: str,
    prefix: Optional[str],
    versioned: bool,
    recursive: bool,
) -> Iterator[dict[str, Any]]:
    """Paginate an S3 bucket listing, yielding tagged dicts.

    Each yielded dict has a '_type' key:
      'version'       - object version (from Versions in list_object_versions)
      'delete_marker' - deletion marker (from DeleteMarkers)
      'prefix'        - common prefix directory (from CommonPrefixes)

    For non-versioned listing, objects from Contents are tagged 'version'.
    """
    kwargs = {'Bucket': bucket_name}
    if prefix:
        kwargs['Prefix'] = prefix
    if not recursive:
        kwargs['Delimiter'] = '/'

    if versioned:
        paginator = client.get_paginator('list_object_versions')
        for page in paginator.paginate(**kwargs):
            for v in page.get('Versions', []):
                v['_type'] = 'version'
                yield v
            for dm in page.get('DeleteMarkers', []):
                dm['_type'] = 'delete_marker'
                yield dm
            for cp in page.get('CommonPrefixes', []):
                yield {
                    '_type': 'prefix',
                    'Key': cp['Prefix'],
                    'VersionId': None,
                    'LastModified': None,
                    'IsLatest': None,
                }
    else:
        paginator = client.get_paginator('list_objects_v2')
        for page in paginator.paginate(**kwargs):
            for obj in page.get('Contents', []):
                obj['_type'] = 'version'
                yield obj
            for cp in page.get('CommonPrefixes', []):
                yield {
                    '_type': 'prefix',
                    'Key': cp['Prefix'],
                    'VersionId': None,
                    'LastModified': None,
                    'IsLatest': None,
                }


def get_key_url(
    entry: dict[str, Any],
    bucket_name: str,
    schema: str = 'http',
    versioned: bool = True,
) -> str:
    """Generate an s3:// or http:// url given an entry dict.

    Parameters
    ----------
    entry : dict
        Must have 'Key' and optionally 'VersionId'.
    bucket_name : str
    schema : {'http', 's3'}
    versioned : bool
        If True and entry has a VersionId, append ?versionId=...
    """
    name_urlquoted = urlquote(entry['Key'])
    if schema == 'http':
        url = "http://{}.s3.amazonaws.com/{}".format(bucket_name, name_urlquoted)
    elif schema == 's3':
        url = "s3://{}/{}".format(bucket_name, name_urlquoted)
    else:
        raise ValueError(schema)
    version_id = entry.get('VersionId')
    if versioned and version_id is not None:
        url += "?versionId={}".format(version_id)
    return url


def get_version_for_key(k: dict[str, Any], fmt: str = '0.0.%Y%m%d') -> Optional[str]:
    """Given a key dict return a version string for tagging.

    Uses 0.0.YYYYMMDD by default.
    """
    if k.get('_type') == 'prefix':
        return None
    last_modified = k.get('LastModified')
    if last_modified is None:
        return None
    # boto3 returns datetime objects
    if isinstance(last_modified, datetime):
        t = last_modified.timestamp()
    else:
        # fallback for string timestamps
        from datalad.support.network import iso8601_to_epoch
        t = iso8601_to_epoch(last_modified)
    return time.strftime(fmt, time.gmtime(t))


def _strip_prefix(s: Optional[str], prefix: str) -> Optional[str]:
    """A helper to strip the prefix from the string if present"""
    return s[len(prefix):] if s and s.startswith(prefix) else s


class crawl_s3(object):
    """Given a source bucket and optional prefix, generate s3:// urls for the content

    """
    def __init__(self,
                 bucket,
                 prefix=None,
                 strip_prefix=True,  # either to strip leading prefix if provided
                 url_schema='s3',
                 strategy='naive',
                 versionfx=get_version_for_key,
                 repo=None,
                 ncommits=None,
                 recursive=False,
                 versioned=True,
                 exclude=None,
                 ):
        """

        Parameters
        ----------

        bucket: str
        prefix: str, optional
          Either to remember redirects for subsequent invocations
        strip_prefix: bool, optional
          Either to strip the prefix (if given) off the target paths
        versionfx: function, optional
          If not None, to define a version from the last processed key
        repo: GitRepo, optional
          Under which to store information about latest scraped version
        strategy: {'naive', 'commit-versions'}, optional
          With `naive` strategy no commits are made if there is a deletion,
          or update event, so a single run should result in a single commit
          even though interim different "load" could be added to annex under
          the same filename
        ncommits: int or None, optional
          If specified, used as max number of commits to perform.
          ??? In principle the same effect could be achieved by a node
          raising FinishPipeline after n'th commit
        recursive: bool, optional
          Either to traverse recursively or just list elements at that level
        versioned: bool, optional
          Either to expect bucket to be versioned and demand all versions per
          prefix and generate versioned urls
        exclude: str, optional
          Regular expression to search to decide which files to exclude from
          consideration
        """
        self.bucket = bucket
        if prefix and not prefix.endswith('/'):
            lgr.warning("ATM we assume prefixes to correspond only to directories, adding /")
            prefix += "/"
        self.prefix = prefix
        self.strip_prefix = strip_prefix
        self.url_schema = url_schema
        assert(strategy in {'naive', 'commit-versions'})
        self.strategy = strategy
        self.versionfx = versionfx
        self.repo = repo
        self.ncommits = ncommits
        self.recursive = recursive
        self.versioned = versioned
        self.exclude = exclude

    def __call__(self, data):
        stats = data.get('datalad_stats', None)
        url = "s3://%s" % self.bucket
        if self.prefix:
            url += "/" + self.prefix.lstrip('/')
        providers = Providers.from_config_files()
        downloader = providers.get_provider(url).get_downloader(url)

        # Authenticate and establish connection.
        # The URL may point at just the bucket (no key), so head_object
        # can fail with TargetFileAbsent (404) or ParamValidationError
        # (empty Key string).  Either way the client is now authenticated.
        try:
            _ = downloader.get_status(url)
        except TargetFileAbsent as exc:
            lgr.debug("Initial URL %s lead to not something downloader could fetch: %s", url, exc_str(exc))
        except Exception as exc:
            lgr.debug("Initial URL %s could not be fetched: %s", url, exc_str(exc))
            pass

        # boto3-based datalad exposes .client and ._bucket_name
        if not hasattr(downloader, 'client'):
            raise ImportError(
                "Your datalad version uses the old boto-based S3Downloader. "
                "Please upgrade datalad to a version with boto3 support."
            )
        client = downloader.client
        bucket_name = downloader._bucket_name
        assert client is not None
        assert bucket_name is not None

        if self.repo:
            versions_db = SingleVersionDB(self.repo)
            prev_version = versions_db.version
            if prev_version and not prev_version.get('version-id', None):
                # Situation might arise when a directory contains no files, only
                # directories which we place into subdatasets
                # see https://github.com/datalad/datalad-crawler/issues/68
                # Workaround -- start from scratch
                lgr.warning("stored version-id is empty. Crawling from the beginning")
                prev_version = None
        else:
            prev_version, versions_db = None, None

        # Fetch all entries, sort, proceed
        all_versions = list(_list_bucket(
            client, bucket_name, self.prefix, self.versioned, self.recursive
        ))

        # Comparison becomes tricky whenever as if in our test bucket we have a collection
        # of rapid changes within the same ms, so they couldn't be sorted by last_modified, so we resolve based
        # on them being marked latest, or not being null (as could happen originally), and placing Delete after creation
        # In real life last_modified should be enough, but life can be as tough as we made it for 'testing'
        def kf(k: dict[str, Any], field: str) -> Any:
            """Get field from dict, using appropriate defaults for sorting."""
            val = k.get(field)
            if val is None:
                # For LastModified, use sentinel datetime for consistent sorting
                if field == 'LastModified':
                    return _MIN_DATETIME
                return ''
            return val

        # So ATM it would sort Prefixes first, but that is not necessarily correct...
        # Theoretically the only way to sort Prefix'es with the rest is traverse that Prefix
        # and take latest last_modified there but it is expensive, so -- big TODO if ever ;)
        # ACTUALLY -- may be there is an API call to return sorted by last_modified, then we
        # would need only a single entry in result to determine the last_modified for the Prefix, thus TODO
        cmp = lambda k: (
            kf(k, 'LastModified'),
            k['Key'],
            bool(k.get('IsLatest')),
            k.get('VersionId', 'null') != 'null',
            k['_type'] == 'delete_marker'
        )

        versions_sorted = sorted(all_versions, key=cmp)

        version_fields = ['last-modified', 'name', 'version-id']

        def _last_modified_for_cmp(k: dict[str, Any]) -> str:
            """Return LastModified as iso8601 string for version DB comparison."""
            lm = k.get('LastModified')
            if lm is None:
                return ''
            if isinstance(lm, datetime):
                return lm.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            return lm

        def get_version_cmp(k: dict[str, Any]) -> tuple[str, str, str]:
            # this one will return action version_id so we could uniquely identify
            return _last_modified_for_cmp(k), k['Key'], k.get('VersionId', '')

        if prev_version:
            last_modified_, name_, version_id_ = [prev_version[f] for f in version_fields]
            # roll forward until we get to the element > this
            # to not breed list copies
            for i, k in enumerate(versions_sorted):
                lm, n, vid = get_version_cmp(k)
                if lm > last_modified_:
                    start = i
                    break
                elif lm == last_modified_:
                    # go by name/version_id to be matched and then switch to the next one
                    if (n, vid) == (name_, version_id_):
                        start = i+1  # from the next one
                        if stats:
                            stats.increment('skipped')
                        break
                stats.increment('skipped')
            versions_sorted = versions_sorted[start:]

        # a set of items which we have already seen/yielded so hitting any of them again
        # would mean conflict/versioning is necessary since two actions came for the same item
        staged = set()
        strategy = self.strategy
        e_prev = None
        ncommits = self.ncommits or 0

        # adding None so we could deal with the last commit within the loop without duplicating
        # logic later outside
        def update_versiondb(e: Optional[dict[str, Any]], force: bool = False) -> None:
            # this way we could recover easier after a crash
            # TODO: config crawl.crawl_s3.versiondb.saveaftereach=True
            if e is not None and (force or True):
                versions_db.version = dict(zip(version_fields, get_version_cmp(e)))
        for e in versions_sorted + [None]:
            filename = e['Key'] if e is not None else None
            if (self.strip_prefix and self.prefix):
                filename = _strip_prefix(filename, self.prefix)
            if filename and self.exclude and re.search(self.exclude, filename):
                stats.skipped += 1
                continue

            if filename in staged or e is None:
                # we should finish this one and commit
                if staged:
                    if self.versionfx and e_prev is not None:
                        version = self.versionfx(e_prev)
                        if version is not None and version not in stats.versions:
                            stats.versions.append(version)
                    if versions_db:
                        # save current "version" DB so we would know where to pick up from
                        # upon next rerun.  Record should contain
                        # last_modified, name, versionid
                        # TODO?  what if e_prev was a DeleteMarker???
                        update_versiondb(e_prev, force=True)
                    if strategy == 'commit-versions':
                        yield updated(data, {'datalad_action': 'commit'})
                        if self.ncommits:
                            ncommits += 1
                            if self.ncommits <= ncommits:
                                lgr.debug("Interrupting on %dth commit since asked to do %d",
                                          ncommits, self.ncommits)
                                break
                    staged.clear()
                if e is None:
                    break  # we are done
            if filename:
                # might be empty if e.g. it was the self.prefix directory removed
                staged.add(filename)
            if e['_type'] == 'version':
                if e['Key'].endswith('/'):
                    # signals a directory for which we don't care explicitly (git doesn't -- we don't! ;) )
                    continue
                url = get_key_url(e, bucket_name, schema=self.url_schema, versioned=self.versioned)
                # Build FileStatus inline from the entry dict
                last_modified = e.get('LastModified')
                mtime = last_modified.timestamp() if isinstance(last_modified, datetime) else None
                url_status = FileStatus(
                    size=e.get('Size'),
                    mtime=mtime,
                    filename=e['Key'],
                )
                # generate and pass along the status right away since we can
                yield updated(
                    data,
                    {
                        'url': url,
                        'url_status': url_status,
                        'filename': filename,
                        'datalad_action': 'annex',
                    })
                update_versiondb(e)
            elif e['_type'] == 'delete_marker':
                if strategy == 'commit-versions':
                    # Since git doesn't care about empty directories for us makes sense only
                    # in the case when DeleteMarker is not pointing to the subdirectory
                    # and not empty (if original directory was removed)
                    if filename and not filename.endswith('/'):
                        yield updated(data, {'filename': filename, 'datalad_action': 'remove'})
                    else:
                        # Situation there is much trickier since it seems that "directory"
                        # could also be a key itself and created/removed which somewhat interferes with
                        # all our logic here
                        # For an interesting example see
                        #  s3://openneuro/ds000217/ds000217_R1.0.0/compressed
                        lgr.info("Ignoring DeleteMarker for %s", filename)

                update_versiondb(e)
            elif e['_type'] == 'prefix':
                # so  we were provided a directory (in non-recursive traversal)
                assert(not self.recursive)
                yield updated(
                    data,
                    {
                        'url': url,
                        'filename': filename.rstrip('/'),
                        'datalad_action': 'directory',
                    }
                )
            else:
                raise ValueError("Don't know how to treat %s" % e)
            e_prev = e
