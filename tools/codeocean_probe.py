#!/usr/bin/env python3
# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""Probe the Code Ocean API to answer the open questions in docs/design/codeocean.md

Answers, for a given capsule:

- does the API answer anonymously (published capsules), or is a token required
  for each of: capsule record, app panel, data asset record, file listing,
  file download URL
- which data assets are attached, at which mount, and whether they are
  internal (files inside Code Ocean) or external (a bucket we could address
  directly with an s3:// URL)
- what a file listing and a (presigned) download URL actually look like, and
  for how long the URL stays valid
- whether the capsule git repo carries per-version release tags

Only the standard library is used, so this can be run anywhere::

    ./tools/codeocean_probe.py 3822095
    ./tools/codeocean_probe.py 3822095 --token "$CODEOCEAN_TOKEN" --json probe.json

Nothing is downloaded and nothing is modified on the server -- all requests are
GET/POST reads.
"""

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

from typing import Optional

# The SDK sends this; older servers reject requests asking for more than they are
MIN_SERVER_VERSION = "4.6.0"


class Result(object):
    """Outcome of a single probed request -- never raises, always reports"""

    def __init__(self, ok, status=None, value=None, error=None):
        self.ok = ok
        self.status = status
        self.value = value
        self.error = error

    def __repr__(self):
        if self.ok:
            return "OK (%s)" % self.status
        return "FAIL (%s: %s)" % (self.status, self.error)

    def asdict(self):
        return {
            'ok': self.ok,
            'status': self.status,
            'error': self.error,
            # keep the payload, it is the point of the exercise
            'value': self.value,
        }


def request(url, token=None, data=None, timeout=30) -> Result:
    """GET (or POST, if `data` is given) `url`, decoding a JSON response"""
    headers = {
        'Min-Server-Version': MIN_SERVER_VERSION,
        'Accept': 'application/json',
    }
    body = None
    if data is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(data).encode()
    if token:
        # Code Ocean uses HTTP Basic with the token as username, empty password
        creds = base64.b64encode(("%s:" % token).encode()).decode()
        headers['Authorization'] = 'Basic %s' % creds

    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = response.read().decode('utf-8', 'replace')
            status = response.status
    except urllib.error.HTTPError as exc:
        return Result(False, status=exc.code,
                      error=exc.read().decode('utf-8', 'replace')[:200])
    except Exception as exc:
        return Result(False, status=None, error=str(exc))

    try:
        return Result(True, status=status, value=json.loads(payload))
    except ValueError:
        return Result(True, status=status, value=payload[:500])


def url_expires_in(signed_url) -> Optional[str]:
    """Extract the lifetime of a presigned S3 URL, if it looks like one"""
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(signed_url).query)
    for key in ('X-Amz-Expires', 'Expires'):
        if key in query:
            return "%s=%s" % (key, query[key][0])
    return None


def probe_api(api, capsule_id, token, results, label):
    """Probe every read endpoint we care about, with or without a token"""
    print("\n== API as %s ==" % label)

    capsule = request("%s/capsules/%s" % (api, capsule_id), token)
    results['capsule'] = capsule.asdict()
    print("  GET capsules/%s                 : %r" % (capsule_id, capsule))
    if capsule.ok and isinstance(capsule.value, dict):
        c = capsule.value
        print("     name=%r slug=%r" % (c.get('name'), c.get('slug')))
        print("     versions=%s" % json.dumps(c.get('versions')))
        print("     submission=%s" % json.dumps(c.get('submission')))
        print("     cloned_from_url=%r article=%s"
              % (c.get('cloned_from_url'), json.dumps(c.get('article'))))

    # Q5: does the API also accept the slug where the web UI shows a number?
    if capsule.ok and isinstance(capsule.value, dict) and capsule.value.get('slug'):
        slug = capsule.value['slug']
        if slug != str(capsule_id):
            by_slug = request("%s/capsules/%s" % (api, slug), token)
            results['capsule_by_slug'] = by_slug.asdict()
            print("  GET capsules/<slug>              : %r" % by_slug)

    panel = request("%s/capsules/%s/app_panel" % (api, capsule_id), token)
    results['app_panel'] = panel.asdict()
    print("  GET capsules/%s/app_panel       : %r" % (capsule_id, panel))

    assets = []
    if panel.ok and isinstance(panel.value, dict):
        assets = panel.value.get('data_assets') or []
        for a in assets:
            print("     data asset %s kind=%s accessible=%s mount=%r name=%r"
                  % (a.get('id'), a.get('kind'), a.get('accessible'),
                     a.get('mount'), a.get('name')))
    if not assets:
        print("     (no data assets reported -- check whether a token is needed,"
              " or the capsule genuinely has none)")

    # per-version app panels: do attached assets differ between releases?
    versions = []
    if capsule.ok and isinstance(capsule.value, dict):
        versions = [v.get('major_version') for v in (capsule.value.get('versions') or [])]
    results['app_panel_per_version'] = {}
    for major in sorted(set(v for v in versions if v is not None)):
        pv = request("%s/capsules/%s/app_panel?version=%s" % (api, capsule_id, major), token)
        results['app_panel_per_version'][str(major)] = pv.asdict()
        ids = None
        if pv.ok and isinstance(pv.value, dict):
            ids = [a.get('id') for a in (pv.value.get('data_assets') or [])]
        print("  GET app_panel?version=%-3s        : %r assets=%s" % (major, pv, ids))

    computations = request("%s/capsules/%s/computations" % (api, capsule_id), token)
    results['computations'] = computations.asdict()
    n_comp = len(computations.value) if computations.ok and isinstance(computations.value, list) else None
    print("  GET capsules/%s/computations    : %r n=%s" % (capsule_id, computations, n_comp))

    # Now dive into the first accessible data asset: record, listing, signed URL
    results['data_assets'] = {}
    for a in assets:
        asset_id = a.get('id')
        if not asset_id:
            continue
        entry = {}
        results['data_assets'][asset_id] = entry

        record = request("%s/data_assets/%s" % (api, asset_id), token)
        entry['record'] = record.asdict()
        print("  GET data_assets/%s : %r" % (asset_id, record))
        if record.ok and isinstance(record.value, dict):
            r = record.value
            print("     type=%s state=%s files=%s size=%s source_bucket=%s"
                  % (r.get('type'), r.get('state'), r.get('files'), r.get('size'),
                     json.dumps(r.get('source_bucket'))))

        listing = request("%s/data_assets/%s/files" % (api, asset_id), token, data={'path': ''})
        entry['root_listing'] = listing.asdict()
        print("  POST data_assets/%s/files : %r" % (asset_id, listing))

        first_file = None
        if listing.ok and isinstance(listing.value, dict):
            for item in (listing.value.get('items') or [])[:20]:
                print("     %-6s %10s  %s" % (item.get('type'), item.get('size'), item.get('path')))
                if first_file is None and item.get('type') == 'file':
                    first_file = item.get('path')

        if first_file:
            quoted = urllib.parse.quote(first_file)
            urls = request("%s/data_assets/%s/files/urls?path=%s" % (api, asset_id, quoted), token)
            entry['file_urls'] = urls.asdict()
            print("  GET  …/files/urls?path=%s : %r" % (first_file, urls))
            if urls.ok and isinstance(urls.value, dict):
                dl = urls.value.get('download_url', '')
                print("     download_url host=%s %s"
                      % (urllib.parse.urlsplit(dl).netloc, url_expires_in(dl) or '(no expiry in query)'))
        else:
            print("     (no file at the root level to ask a URL for)")

        # one asset is enough to characterise the deployment
        break


def probe_git(git_url, results):
    """Does the capsule git repo exist anonymously, and does it tag releases?"""
    print("\n== git ==")
    print("  %s" % git_url)
    results['git_url'] = git_url
    try:
        out = subprocess.run(
            ['git', 'ls-remote', '--refs', git_url],
            capture_output=True, text=True, timeout=120,
        )
    except Exception as exc:
        results['git'] = {'ok': False, 'error': str(exc)}
        print("  FAILED: %s" % exc)
        return

    if out.returncode != 0:
        results['git'] = {'ok': False, 'error': out.stderr.strip()[:300]}
        print("  anonymous access FAILED: %s" % out.stderr.strip()[:300])
        return

    refs = [line.split('\t')[1] for line in out.stdout.splitlines() if '\t' in line]
    tags = [r for r in refs if r.startswith('refs/tags/')]
    heads = [r for r in refs if r.startswith('refs/heads/')]
    results['git'] = {'ok': True, 'heads': heads, 'tags': tags}
    print("  anonymous access OK")
    print("  branches: %s" % (', '.join(heads) or '(none)'))
    print("  tags    : %s" % (', '.join(tags) or '(none -- versions must be resolved via submission.commit)'))


def probe_git_tree(git_url, results):
    """Shallow-clone to see the top-level layout the crawler will merge in"""
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(
            ['git', 'clone', '--depth', '1', '--quiet', git_url, tmp + '/capsule'],
            capture_output=True, text=True, timeout=300,
        )
        if out.returncode != 0:
            print("  clone failed: %s" % out.stderr.strip()[:300])
            return
        listing = subprocess.run(
            ['git', '-C', tmp + '/capsule', 'ls-tree', '--name-only', 'HEAD'],
            capture_output=True, text=True,
        )
        entries = listing.stdout.split()
        results['git_toplevel'] = entries
        print("  top level: %s" % ', '.join(entries))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('capsule_id', help="capsule id as in the web URL, e.g. 3822095")
    parser.add_argument('--domain', default='https://codeocean.com',
                        help="Code Ocean deployment (default: %(default)s)")
    parser.add_argument('--git-domain', default='https://git.codeocean.com',
                        help="git host serving capsule repos (default: %(default)s)")
    parser.add_argument('--token', default=None,
                        help="API token; without it only the anonymous probe runs")
    parser.add_argument('--anonymous-only', action='store_true',
                        help="skip the authenticated probe even if a token is given")
    parser.add_argument('--skip-git', action='store_true', help="skip the git probes")
    parser.add_argument('--json', metavar='FILE', default=None,
                        help="also dump every response to FILE for later reference")
    args = parser.parse_args(argv)

    api = args.domain.rstrip('/') + '/api/v1'
    results = {'domain': args.domain, 'capsule_id': args.capsule_id}

    results['anonymous'] = {}
    probe_api(api, args.capsule_id, None, results['anonymous'], 'anonymous')

    if args.token and not args.anonymous_only:
        results['authenticated'] = {}
        probe_api(api, args.capsule_id, args.token, results['authenticated'], 'authenticated')
    elif not args.token:
        print("\n(no --token given: skipping the authenticated probe)")

    if not args.skip_git:
        git_url = "%s/capsule-%s.git" % (args.git_domain.rstrip('/'), args.capsule_id)
        probe_git(git_url, results)
        if results.get('git', {}).get('ok'):
            probe_git_tree(git_url, results)

    if args.json:
        with open(args.json, 'w') as f:
            json.dump(results, f, indent=2, sort_keys=True)
        print("\nFull responses written to %s" % args.json)

    return 0


if __name__ == '__main__':
    sys.exit(main())
