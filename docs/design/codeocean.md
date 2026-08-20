# Crawling Code Ocean capsules

Status: design proposal (no implementation yet).
Reference capsule used throughout: <https://codeocean.com/capsule/3822095/tree/v2>,
whose code is also available as <https://git.codeocean.com/capsule-3822095.git>.

## 1. Anatomy of a capsule

A capsule is not a single downloadable blob.  It is assembled at run time from
three independently addressable pieces, which is exactly why a crawler (rather
than a plain `datalad download-url`) is the right tool:

| Piece | Lives in the capsule at | Where it actually comes from |
|---|---|---|
| code, environment definition, capsule metadata | `/code`, `/environment`, `/metadata` | the capsule's git repository (`https://git.codeocean.com/capsule-<id>.git`) |
| data | `/data/<mount>` | one or more **data assets** attached to the capsule; each is a separate object with its own id, permissions and file tree |
| results | `/results` | outputs of **computations**; optionally captured into result data assets |

So the "git component" the user already found is not just a nice-to-have base —
it is the *only* source for code, because there is **no capsule-files endpoint in
the API at all** (see §2).  Conversely git carries no data, because data assets
are never committed into the capsule repo.  A faithful DataLad dataset therefore
has to marry the two.

## 2. The API surface

Verified against the official Python SDK `codeocean` 0.16.0 (read from the wheel
on PyPI: `codeocean/capsule.py`, `data_asset.py`, `computation.py`,
`models/folder.py`), which is a thin, complete mirror of the REST API.

* Base URL: `https://<domain>/api/v1/` (`https://codeocean.com/api/v1/` for the
  public deployment; enterprise installs use their own domain).
* Auth: HTTP **Basic**, with the API token as the *username* and an empty
  password (`session.auth = (token, "")`).
* The SDK also sends `Min-Server-Version: 4.6.0` and `Content-Type: application/json`.

Endpoints that matter for crawling:

| Method + route | Returns / notes |
|---|---|
| `GET capsules/{id}` | capsule record: `name`, `slug`, `description`, `field`, `tags`, `owner`, `created`, `cloned_from_url`, `original_capsule`, `release_capsule`, `article` (DOI, journal, publish_time), `submission` (commit hash, verified…), `versions[]` (`major_version`, `minor_version`, `release_time`, `doi`) |
| `GET capsules/{id}/app_panel?version=N` | **the capsule → data-asset link**: `data_assets[]` with `id`, `mount`, `name`, `kind` (`internal`/`external`/`combined`), `accessible`; plus parameters/results declarations.  `version=N` makes it *per released version* |
| `GET capsules/{id}/computations` | computations run in the capsule |
| `POST capsules/search` | paginated search (`query`, `limit`≤1000, `next_token`, `sort_field`, `status=release`) — discovery for a superdataset |
| `GET data_assets/{id}` | `name`, `description`, `tags`, `type` (`dataset`/`result`), `state`, `files` (count), `size`, `created`, `source_bucket` (`bucket`, `prefix`, `external`), `provenance`, `custom_metadata` |
| `POST data_assets/{id}/files` body `{"path": "..."}` | one directory level: `items[] = {name, path, type: file\|folder, size}`.  Empty path = root ⇒ recurse to walk the tree |
| `GET data_assets/{id}/files/urls?path=...` | `{download_url, view_url}` — **signed, expiring** URLs |
| `GET data_assets/{id}/files/download_url?path=...` | deprecated predecessor returning `{url}`; supported until Aug 2026 |
| `POST computations/{id}/results` body `{"path": ...}` | same `Folder` shape for `/results` |
| `GET computations/{id}/results/urls?path=...` | signed URLs for a result file |

Notably absent: anything like `capsules/{id}/files`.  Code comes from git, full
stop.

## 3. Target dataset layout

Mirror the capsule's own runtime layout so that a `datalad get . && cd .. &&
docker run` reproduces what Code Ocean mounts:

```
<dataset>/
├── code/                     ─┐
├── environment/               ├─ verbatim from git.codeocean.com, original history
├── metadata/                 ─┘
├── REPRODUCING.md            ─┘
├── data/
│   └── <mount>/…             ─── annexed, one subtree per attached data asset
├── results/                  ─── optional, from a chosen computation
└── .datalad/meta/codeocean/
    ├── capsule.json
    ├── app_panel-v<N>.json
    └── data_assets/<asset-id>.json
```

`data/<mount>` uses the `mount` value straight from the app panel, so paths
match `/data/<mount>` inside the capsule.

## 4. Branch layout: how git history and crawled data are married

This is the answer to "worse comes to worst we could just add it as a remote":
we can do better than a detached remote, and cheaply.

```
codeocean-git/master  (remote-tracking, fetched verbatim — never rewritten)
        │
        └──► codeocean/code   (local branch, fast-forward only)
                    ╲
                     ╲   merge --allow-unrelated-histories
incoming ─────────────►╳──► master
(data assets, metadata)
```

* remote `codeocean-git` = `https://git.codeocean.com/capsule-<id>.git`, fetched
  by the pipeline.  Its history is preserved bit-for-bit, so upstream commits,
  authorship and any release tags stay verifiable.
* `incoming` is the usual crawler branch: annexed data-asset files plus the
  metadata JSONs, tracked by a `statusdb` so re-crawls are incremental.
* `master` is the merge of the two.  The first merge needs unrelated histories:
  `Annexificator.merge_branch` forwards `**merge_kwargs` to `GitRepo.merge`, so
  `annex.merge_branch('codeocean/code', allow_unrelated=True)` should suffice —
  worth confirming against the installed datalad, otherwise a two-line custom
  node calling `git merge --allow-unrelated-histories` does it.

Later re-crawls just fetch `codeocean-git`, fast-forward `codeocean/code` and
re-merge; the crawler's `skip_no_changes` logic keeps that a no-op when nothing
moved upstream.

If the capsule was itself cloned from an external repo (`cloned_from_url` on the
capsule record), that URL is worth recording as another remote — it is the
upstream of the upstream.

## 5. The hard problem: signed URLs expire

`Annexificator` ultimately runs `git annex addurl <url>`, and the URL it is
handed is recorded in the annex branch forever.  A Code Ocean
`download_url` is a presigned S3 URL valid for minutes-to-an-hour, so a naive
crawl produces a dataset whose `datalad get` starts failing the same afternoon —
the content is there for whoever crawled it and unobtainable for everybody else.
Three tiers, in order of preference:

### 5a. External data assets → register the real S3 URI

When `data_asset.source_bucket.bucket` is set (`kind == "external"`, i.e. the
data was never copied into Code Ocean), the durable address is
`s3://<bucket>/<prefix>/<path>`.  Register that and the existing datalad S3
machinery (`datalad_crawler/nodes/s3.py`, the `datalad` special remote) handles
retrieval, with public buckets needing no Code Ocean account at all.  This is
the best possible outcome and costs nothing extra to support.

### 5b. Internal data assets → a `dl+codeocean:` special remote

For internal assets the only durable identifier is (`data_asset_id`, `path`).
Ship an external special remote — `git-annex-remote-codeocean`, exactly
analogous to `datalad-archives` and its `dl+archive:` URLs — that:

* `CLAIMURL` / `CHECKURL` for `dl+codeocean://<domain>/data_assets/<id>/<path>`;
* on `TRANSFER RETRIEVE`, calls `GET data_assets/<id>/files/urls?path=<path>`
  with the user's token, then downloads the freshly minted `download_url`;
* `CHECKPRESENT` = the same call succeeding (or a `POST …/files` listing hit,
  which is cheaper and does not mint a URL).

Then the crawl records a URL that is stable for as long as the capsule exists,
and any user with a token (or none, if the capsule is public and the API allows
anonymous reads — see §8) can `datalad get`.

Practical way to get there without touching `Annexificator`: let it annex the
file through the presigned URL as today (real download, real checksum), then
follow it with a small node that rewrites the recorded URL:

```python
def register_stable_url(data):
    fpath = relpath(data['filepath'], annex.repo.path)
    key = annex.repo.call_annex_oneline(['lookupkey', fpath])
    annex.repo.call_annex(['registerurl', key, data['codeocean_url']])
    annex.repo.call_annex(['rmurl', fpath, data['url']])   # the presigned one
    yield data
```

Files that land in git rather than annex (per `annex.largefiles`) have no URL
and need no rewriting — guard on `lookupkey` returning empty.

### 5c. Fallback

If neither applies (or before the special remote exists), still crawl: the
content is correct and checksummed, the metadata records
`data_asset_id` + `path` per file in `.datalad/meta/codeocean/`, and the URLs can
be re-registered later by a one-off script.  Just do not pretend the dataset is
self-servicing — say so in the README the pipeline generates.

Corollary: `mode='fast'`/`'relaxed'` are not usable here.  They skip the
download, and a recorded presigned URL that was never fetched is worthless.

## 6. Versions

`GET capsules/{id}` returns `versions[]` with `major_version`, `minor_version`,
`release_time` and a per-version DOI; `/tree/v2` in the web UI is major version 2.
Crucially `app_panel?version=N` reports the data assets *as attached in that
version*, so a version-by-version reconstruction is possible rather than only a
snapshot of HEAD:

for each released version, oldest first —
1. reset `codeocean/code` to that version's commit (from the release tag in the
   git repo, or `submission.commit`; §8 lists this as unverified),
2. crawl the data assets that `app_panel?version=N` reports,
3. merge into `master`, commit, and `git tag codeocean/v<major>.<minor>` with the
   DOI in the tag message.

This gives a DataLad dataset whose history is a real history, not a series of
"crawled on <date>" snapshots.  The crawler's `commit_versions` /
`remove_other_versions` machinery targets per-file versioned URLs (the openfmri
case) and does not fit; plain tags do.

Default behaviour: crawl the latest release only, with `versions='all'` opting
into the full walk.

## 7. Pipeline shape

`datalad_crawler/pipelines/codeocean.py`, following the `xnat.py` idiom (a small
client class + node factories):

```python
class CodeOceanClient(object):
    """Thin wrapper over https://<domain>/api/v1/, using datalad downloaders"""
    def __init__(self, domain='https://codeocean.com', token=None): ...
    def get_capsule(self, capsule_id): ...
    def get_app_panel(self, capsule_id, version=None): ...
    def get_data_asset(self, asset_id): ...
    def walk_data_asset(self, asset_id, path=''):
        """Recursive generator over POST data_assets/{id}/files -> (path, size)"""
    def get_file_urls(self, asset_id, path): ...


def pipeline(capsule_id,
             domain='https://codeocean.com',
             versions='latest',        # 'latest' | 'all' | '2' | '2.1'
             data=True,                # crawl attached data assets
             results=False,            # crawl results of computations
             git_url=None,             # default https://git.codeocean.com/capsule-<id>.git
             largefiles='largerthan=100kb'):
    annex = Annexificator(
        create=False, statusdb='json',
        special_remotes=[DATALAD_SPECIAL_REMOTE],
        largefiles=largefiles,
        skip_problematic=False,
    )
    return [
        fetch_capsule_git(git_url or f'https://git.codeocean.com/capsule-{capsule_id}.git'),
        crawl_capsule_metadata(client, capsule_id),      # -> .datalad/meta/codeocean/*.json
        annex.switch_branch('incoming'),
        [
            crawl_data_assets(client, capsule_id, version),  # yields url/filename/path per file
            annex,
            register_stable_url,
        ],
        annex.switch_branch('master'),
        annex.merge_branch('incoming', allow_unrelated=False),
        annex.merge_branch('codeocean/code', allow_unrelated=True),
        annex.finalize(tag=True, cleanup=True),
    ]


def superdataset_pipeline(query=None, domain='https://codeocean.com', **kw):
    """One subdataset per capsule matching a POST capsules/search query"""
    ...
    annex.initiate_dataset(template='codeocean', data_fields=['capsule_id'], existing='skip')
```

Usage would then be:

```sh
datalad crawl-init --save --template=codeocean capsule_id=3822095 versions=all
datalad crawl
```

## 8. Credentials

Follow the `gh.py` idiom rather than inventing a new mechanism: try a stored
datalad credential first, fall back to config.

```python
from datalad.downloaders.credentials import Token
token = Token('codeocean.com')()['token']        # or cfg.get('datalad.codeocean.token')
```

For downloads through datalad's downloaders, a provider entry pins the auth type
(token-as-username Basic):

```ini
[provider:codeocean]
url_re = https://codeocean\.com/api/.*
authentication_type = http_basic_auth
credential = codeocean

[credential:codeocean]
type = user_password        # user = <API token>, password = ""
```

## 9. Open questions — must be probed against the live service

I could not verify these from here: this sandbox's egress policy blocks
`codeocean.com` and `docs.codeocean.com`, so everything above comes from the SDK
source and the capsule layout, not from live responses.  `tools/codeocean_probe.py`
in this branch answers all of them in one run; the answers change how much of §5
is needed.

1. **Anonymous access.** `git.codeocean.com` clearly serves public capsules
   without credentials (the reference capsule was cloned anonymously).  Does
   `GET /api/v1/capsules/3822095` — and more importantly `app_panel`,
   `data_assets/{id}/files` and `files/urls` — also work without a token for a
   *published* capsule?  If yes, crawling the Open Science Library needs no
   account at all, and the special remote of §5b can retrieve anonymously.
2. **Are published-capsule data assets external?**  If public capsule data lives
   in a public S3 bucket (`source_bucket` populated), §5a covers everything and
   §5b becomes optional.
3. **Release tags in the capsule git repo.**  Does `capsule-3822095.git` carry
   `v1`/`v2` tags, or must versions be resolved via `submission.commit`?  This
   decides whether §6's per-version walk is straightforward.
4. **Presigned URL TTL** (`X-Amz-Expires` on the returned `download_url`) —
   sets the practical ceiling on how long a single crawl pass may take before
   URLs minted early go stale.
5. **Slug vs numeric id.**  The web URL uses `3822095`; the API `Capsule` record
   carries both `id` and `slug`.  Which one do the API routes accept?
6. Whether `/results` is worth crawling by default (published capsules ship a
   "Reproducible Run" result set, but it may be large and is derived data).

## 10. Implementation order

1. Run `tools/codeocean_probe.py` against a published capsule and a private one;
   record answers to §9 here.
2. `datalad_crawler/pipelines/codeocean.py`: client + metadata + git-remote node
   + data-asset crawl, snapshot of the latest version only, presigned URLs
   recorded as-is (§5c).  Tests in the `test_xnat.py` style with recorded API
   responses.
3. `git-annex-remote-codeocean` + the `register_stable_url` node (§5b), plus
   `s3://` registration for external assets (§5a).
4. Per-version history walk and tagging (§6).
5. `superdataset_pipeline` over `POST capsules/search` (§7).
