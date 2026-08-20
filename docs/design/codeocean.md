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

## 5. The hard problem: signed URLs expire — solved with datalad-next's *uncurl*

`Annexificator` ultimately runs `git annex addurl <url>`, and the URL it is
handed is recorded in the annex branch forever.  A Code Ocean
`download_url` is a presigned S3 URL valid for minutes-to-an-hour, so a naive
crawl produces a dataset whose `datalad get` starts failing the same afternoon —
the content is there for whoever crawled it and unobtainable for everybody else.

The fix is *not* to write another special remote.  datalad-next's
[uncurl](https://docs.datalad.org/projects/next/en/stable/generated/datalad_next.annexremotes.uncurl.html)
already provides the whole git-annex side of it, and it is extensible in exactly
the direction we need.

### 5a. What uncurl gives us for free

Read from `datalad_next/annexremotes/uncurl.py` and
`datalad_next/url_operations/any.py` (datalad-next 1.6.0):

* **A pseudo-URL scheme is enough.**  `claimurl()` claims any URL that a
  registered URL handler supports (or, when `match` expressions are configured,
  any URL matching one).  `checkurl()` → `stat()`, `transfer_retrieve()` →
  `download()`, `checkpresent()` → `stat()`.  Everything annex-facing is done.
* **Handlers are pluggable**, either purely by config —
  `datalad.url-handler.<url-regex>.class` (plus an optional `.kwargs` JSON blob)
  — or by inserting into `datalad_next.url_operations.any._url_handlers`.
* **Credentials come from datalad-next's credential system**, with interactive
  prompting and secure storage, rather than the core "providers" mechanism.
* **On-access URL rewriting.**  `match` expressions decompose a recorded URL
  into named groups, and a `url` template recomposes it.  Both can live in
  *committed* dataset config (`remote.<name>.uncurl-url`,
  `remote.<name>.uncurl-match` in `.datalad/config`), so clones inherit them and
  a storage migration on Code Ocean's side is a one-line config change instead
  of rewriting URLs for every key in every dataset.

### 5b. What still needs writing: a ~150-line URL handler

uncurl's templates are static string formatting; they cannot perform the
two-step handshake Code Ocean requires (`GET data_assets/{id}/files/urls?path=…`
→ JSON → presigned URL → download).  That step belongs in a `UrlOperations`
handler:

```python
class CodeOceanUrlOperations(HttpUrlOperations):
    """Handles codeocean+https://<domain>/data_assets/<id>/<path>"""
    def stat(self, url, *, credential=None, timeout=None):
        # POST data_assets/{id}/files {"path": dirname} -> size of `path`
    def download(self, from_url, to_path, *, credential=None, hash=None, timeout=None):
        # GET data_assets/{id}/files/urls?path=... -> download_url (fresh, valid now)
        # then stream it with the inherited HttpUrlOperations machinery
```

**This exact pattern is already deployed**: `datalad-publicneuro` ships
`PublicNeuroHttpUrlOperations` for `publicneuro+https://<dataset-id>/<path>`,
whose `download()` performs a three-request handshake (authenticate → item info
→ mint download link) before streaming.  It registers the handler in the
extension's `__init__.py`:

```python
from datalad_next.url_operations import any
any._url_handlers['publicneuro\\+https'] = (
    'datalad_publicneuro.url_operations.publicneuro.PublicNeuroHttpUrlOperations',)
```

and ships a three-line console script so users get a remote that has the handler
pre-registered:

```python
# git-annex-remote-uncurl-codeocean
from datalad_next.annexremotes import uncurl   # import registers our handler
def main():
    uncurl.main()
```

```sh
git annex initremote uncurl-codeocean type=external \
    externaltype=uncurl-codeocean encryption=none autoenable=true
```

The pure-config alternative needs no console script at all, just stock `uncurl`
plus, in the dataset's `.datalad/config`:

```ini
[datalad "url-handler.codeocean\\+https"]
    class = datalad_crawler.url_operations.codeocean.CodeOceanUrlOperations
```

Note `_url_handlers` is private API (datalad-next's own comment flags the
missing entry-point mechanism), so prefer the config route and keep the
`__init__.py` insertion as the convenience path.

### 5c. Consequences for the crawl itself

Because uncurl claims `codeocean+https:` URLs at `addurl` time, the crawler can
record the **stable** URL directly and let uncurl do the actual download.  No
presigned URL ever enters git history, and the `registerurl`/`rmurl` rewriting
dance of an earlier draft disappears.

One wrinkle: `Annexificator.__call__` stats the URL through datalad-core's
`Providers`, which knows nothing of `codeocean+https:`.  It honours a
pre-supplied status though — `_get_url_status()` returns `data['url_status']` if
present — and the file listing already told us the size, so the crawl node just
yields it:

```python
yield {
    'url': f'codeocean+https://{domain}/data_assets/{asset_id}/{path}',
    'url_status': FileStatus(size=item['size']),   # datalad.support.status
    'filename': op.basename(path),
    'path': op.join('data', mount, op.dirname(path)),
}
```

### 5d. External data assets need nothing at all

When `data_asset.source_bucket.bucket` is set (`kind == "external"`, the data was
never copied into Code Ocean), the durable address is the bucket itself.
Recording `https://<bucket>.s3.amazonaws.com/<prefix>/<path>` makes stock uncurl
(or plain git-annex, or the core `datalad` remote) sufficient — no handler, no
Code Ocean account for public buckets.  Worth detecting and preferring, and it
is the first thing §9's probe checks.

### 5e. Cost of the dependency

`datalad get` on such a dataset requires datalad-next (and, for internal assets,
datalad-crawler's handler) on the consumer's machine.  That is a real
constraint, but a far smaller one than an unmaintained bespoke special remote —
and for external assets (§5d) it does not apply.

Corollary either way: `mode='fast'`/`'relaxed'` remain unusable — they skip the
download, so nothing is checksummed.

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
        # `init_datalad_remote` derives externaltype from the remote name,
        # so the name must match the shipped console script (§5b)
        special_remotes=['uncurl-codeocean'],
        largefiles=largefiles,
        skip_problematic=False,
    )
    return [
        fetch_capsule_git(git_url or f'https://git.codeocean.com/capsule-{capsule_id}.git'),
        crawl_capsule_metadata(client, capsule_id),      # -> .datalad/meta/codeocean/*.json
        annex.switch_branch('incoming'),
        [
            # yields codeocean+https:// urls + url_status per file (§5c)
            crawl_data_assets(client, capsule_id, version),
            annex,
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

Two consumers, two systems, which is unavoidable while datalad-crawler sits on
datalad-core and uncurl sits on datalad-next.

*Crawl time* (the pipeline's own API calls) follows the `gh.py` idiom — a stored
datalad credential, falling back to config:

```python
from datalad.downloaders.credentials import Token
token = Token('codeocean.com')()['token']        # or cfg.get('datalad.codeocean.token')
```

with a provider entry pinning the auth type (token-as-username Basic) for
anything routed through datalad-core downloaders:

```ini
[provider:codeocean]
url_re = https://codeocean\.com/api/.*
authentication_type = http_basic_auth
credential = codeocean

[credential:codeocean]
type = user_password        # user = <API token>, password = ""
```

*Get time* (the URL handler under uncurl) uses datalad-next's credential system
via `DataladAuth`, which prompts and offers to store on first use.  Caveat worth
budgeting for: `DataladAuth` keys off the server's `WWW-Authenticate` header, and
`datalad-publicneuro` had to subclass it precisely because their server omits
that header on 401.  If Code Ocean does the same (§9.7), expect a similar small
subclass that injects `Basic realm="codeocean"`.

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
   account at all, and the uncurl handler of §5b can retrieve anonymously.
2. **Are published-capsule data assets external?**  If public capsule data lives
   in a public S3 bucket (`source_bucket` populated), §5d covers everything and
   the handler of §5b becomes optional.
3. **Release tags in the capsule git repo.**  Does `capsule-3822095.git` carry
   `v1`/`v2` tags, or must versions be resolved via `submission.commit`?  This
   decides whether §6's per-version walk is straightforward.
4. **Presigned URL TTL** (`X-Amz-Expires` on the returned `download_url`) —
   sets the practical ceiling on how long a single crawl pass may take before
   URLs minted early go stale.
5. **Slug vs numeric id.**  The web URL uses `3822095`; the API `Capsule` record
   carries both `id` and `slug`.  Which one do the API routes accept?
7. **Does a 401 from the API carry a `WWW-Authenticate` header?**  Decides
   whether stock `DataladAuth` works in the URL handler or needs the
   `datalad-publicneuro`-style subclass (§8).
8. Whether `/results` is worth crawling by default (published capsules ship a
   "Reproducible Run" result set, but it may be large and is derived data).

## 10. Implementation order

1. Run `tools/codeocean_probe.py` against a published capsule and a private one;
   record answers to §9 here.
2. `datalad_crawler/url_operations/codeocean.py`: the `UrlOperations` handler
   (§5b) — it is small, standalone and testable against recorded responses, and
   everything else depends on it.
3. `datalad_crawler/pipelines/codeocean.py`: client + metadata + git-remote node
   + data-asset crawl, snapshot of the latest version only, recording
   `codeocean+https:` URLs (§5c) and bucket URLs where available (§5d).  Tests
   in the `test_xnat.py` style with recorded API responses.
4. Per-version history walk and tagging (§6).
5. `superdataset_pipeline` over `POST capsules/search` (§7).
