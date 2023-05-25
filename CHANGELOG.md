# 1.0.1 (Thu May 25 2023)

#### 🏠 Internal

- Swtich release action from EOLed 3.6 (lead to failed release upload to pypi) to 3.11 [#135](https://github.com/datalad/datalad-crawler/pull/135) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 1.0.0 (Thu May 25 2023)

#### 💥 Breaking Change

- [gh-actions](deps): Bump codespell-project/actions-codespell from 1 to 2 [#133](https://github.com/datalad/datalad-crawler/pull/133) ([@dependabot[bot]](https://github.com/dependabot[bot]))

#### 🐛 Bug Fix

- codespell: config, workflow + fixes [#131](https://github.com/datalad/datalad-crawler/pull/131) ([@yarikoptic](https://github.com/yarikoptic))

#### 🧪 Tests

- Add Python 3.10 and 3.11 into travis CI testing, switch Travis env to newer focal, and drop testing across different annex repo versions [#134](https://github.com/datalad/datalad-crawler/pull/134) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- [@dependabot[bot]](https://github.com/dependabot[bot])
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.9 (Mon Oct 31 2022)

#### 🏠 Internal

- Re-release due to PyPi maintenance [#130](https://github.com/datalad/datalad-crawler/pull/130) ([@bpoldrack](https://github.com/bpoldrack))

#### Authors: 1

- Benjamin Poldrack ([@bpoldrack](https://github.com/bpoldrack))

---

# 0.9.8 (Fri Oct 28 2022)

#### 🐛 Bug Fix

- Fix metadata import and dependency on datalad-deprecated [#129](https://github.com/datalad/datalad-crawler/pull/129) ([@bpoldrack](https://github.com/bpoldrack))

#### Authors: 1

- Benjamin Poldrack ([@bpoldrack](https://github.com/bpoldrack))

---

# 0.9.7 (Mon Oct 24 2022)

#### 🏠 Internal

- Guard usage of the legacy method  `meta_aggregate`, add datalad-deprecated into tests dependencies [#126](https://github.com/datalad/datalad-crawler/pull/126) ([@christian-monch](https://github.com/christian-monch) [@yarikoptic](https://github.com/yarikoptic))
- Update GitHub Actions action versions [#128](https://github.com/datalad/datalad-crawler/pull/128) ([@jwodder](https://github.com/jwodder))
- Set action step outputs via $GITHUB_OUTPUT [#127](https://github.com/datalad/datalad-crawler/pull/127) ([@jwodder](https://github.com/jwodder))

#### Authors: 3

- Christian Mönch ([@christian-monch](https://github.com/christian-monch))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.6 (Fri Sep 16 2022)

#### 🏠 Internal

- Move definition of `HANDLE_META_DIR` into cralwer [#125](https://github.com/datalad/datalad-crawler/pull/125) ([@christian-monch](https://github.com/christian-monch))
- RF: remove datalad_deprecated dependency [#119](https://github.com/datalad/datalad-crawler/pull/119) ([@yarikoptic](https://github.com/yarikoptic))
- BF: import __version__ straight from datalad. not deprecated datalad.version [#120](https://github.com/datalad/datalad-crawler/pull/120) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- Christian Mönch ([@christian-monch](https://github.com/christian-monch))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.5 (Wed Aug 03 2022)

#### 🐛 Bug Fix

- DOC: Set language in Sphinx config to en [#118](https://github.com/datalad/datalad-crawler/pull/118) ([@adswa](https://github.com/adswa))

#### 🧪 Tests

- Switch to pytest [#117](https://github.com/datalad/datalad-crawler/pull/117) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### Authors: 3

- Adina Wagner ([@adswa](https://github.com/adswa))
- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.4 (Wed May 25 2022)

#### 🏠 Internal

- BF: nose is ATM run time requirement as well of crawler (see comment) [#115](https://github.com/datalad/datalad-crawler/pull/115) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.3 (Wed Nov 10 2021)

#### 🐛 Bug Fix

- RF: move (and minimal RF) get_func_kwargs_doc from core [#113](https://github.com/datalad/datalad-crawler/pull/113) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.2 (Fri Nov 05 2021)

#### 🐛 Bug Fix

- RF: moved support/versions.py from datalad core [#111](https://github.com/datalad/datalad-crawler/pull/111) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- RF: Adjust for add-archive-content refactoring in datalad core [#112](https://github.com/datalad/datalad-crawler/pull/112) ([@adswa](https://github.com/adswa))

#### Authors: 2

- Adina Wagner ([@adswa](https://github.com/adswa))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.1 (Sat Oct 02 2021)

#### 🐛 Bug Fix

- BF: Do not pass -b master on older gits -- not supported [#107](https://github.com/datalad/datalad-crawler/pull/107) ([@yarikoptic](https://github.com/yarikoptic))

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.9.0 (Wed Sep 29 2021)

#### 🚀 Enhancement

- Minimal changes to "ensure" master branch being the default for tests [#106](https://github.com/datalad/datalad-crawler/pull/106) ([@yarikoptic](https://github.com/yarikoptic))

#### 🐛 Bug Fix

- Discontinue use of obsolete Repo.add_submodule() [#105](https://github.com/datalad/datalad-crawler/pull/105) ([@mih](https://github.com/mih))

#### Authors: 2

- Michael Hanke ([@mih](https://github.com/mih))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.8.5 (Mon Apr 19 2021)

#### 🐛 Bug Fix

- Codespelled some obvious typos etc [#100](https://github.com/datalad/datalad-crawler/pull/100) ([@yarikoptic](https://github.com/yarikoptic))

#### 🏠 Internal

- Add beforeCommitChangelog hook for updating datalad_crawler/version.py [#98](https://github.com/datalad/datalad-crawler/pull/98) ([@jwodder](https://github.com/jwodder))
- Use Markdown README as-is on PyPI [#99](https://github.com/datalad/datalad-crawler/pull/99) ([@jwodder](https://github.com/jwodder))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.8.4 (Thu Apr 15 2021)

#### 🐛 Bug Fix

- Add dependency on datalad_deprecated [#94](https://github.com/datalad/datalad-crawler/pull/94) ([@mih](https://github.com/mih))

#### Authors: 1

- Michael Hanke ([@mih](https://github.com/mih))

---

# 0.8.3 (Tue Apr 13 2021)

#### 🐛 Bug Fix

- Set up workflow with auto for releasing & PyPI uploads [#86](https://github.com/datalad/datalad-crawler/pull/86) ([@jwodder](https://github.com/jwodder) [@yarikoptic](https://github.com/yarikoptic))

#### Authors: 2

- John T. Wodder II ([@jwodder](https://github.com/jwodder))
- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

# 0.8.2 (Mar 19, 2021) -- Hunt the corpses

- RF: Replace custom SafeConfigParserWithIncludes with standard ConfigParser
- BF: gh - handle situation when cloned repo is still empty

# 0.8.1 (Feb 25, 2021) -- Pay the price

- Fix up use of protected datalad's interface for auth to github.
  Boosted DataLad version dependency to 0.13.6

# 0.8.0 (Jan 03, 2021) -- Good as New

- Making compatible with recent DataLad by using new WitlessRunner and
  not older unused features.

# 0.7.0 (Nov 20, 2020) -- Cherish the moment

- RF: stop using `_{git,annex}_custom_command` to allow DataLad core
  progress forward without "breaking" the crawler

# 0.6.0 (Jul 13, 2020) -- Honoring Kyle (who never adds a release "name")

- ENH: fix enabling special remotes when working ith recent (as of 202006)
  git-annex
- NF: gh (for github) and xnat crawler pipelines

# 0.5.0 (Feb 27, 2020) -- Future is bright

- DataLad 0.12 is now minimal version.  Codebase is now compatible with current
  DataLad 0.12.2-293-gd5fcb4833
  - uses less of GitPython functionality
- OpenfMRI pipeline tests "relaxed" (no commit counts etc)
- s3 node - be robust in case of no previous version-id known

# 0.4.4 (Nov 20, 2019) -- ... despite some mocking

- ENH: `s3_simple` pipeline got additional option `drop_immediately` to
  drop files immediately upon having them annexed
- RF: `mock` is explicitly listed as a dependency for testing since DataLad
  0.12.x will be PY3 only and could use built-in `unittest.mock`

# 0.4.3 (Oct 30, 2019) -- ... and help each other

- MNT: More changes for compatibility with developmental DataLad (#62)

# 0.4.2 (Oct 30, 2019) -- Friends should stick together ...

- BF: Prevent sorting error on missing attribute (#45)
- BF: enclose "if else" into () since it has lower precedence than + (#43)
- MNT: Adjust imports for compatibility with developmental DataLad (#53)
- MNT: Update save() call for compatibility with new save (#42)

# 0.4.1 (Jun 20, 2019) -- Let us all stay friends

- Compatibility layer with 0.12 series of DataLad changing API
  (no backend option for `create`)

# 0.4 (Mar 14, 2019) -- There is more to life than a Pi

Primarily a variety of fixes and small enhancements. The only notable
change is stripping away testing/support of git-annex direct mode.

- do not depend on a release candidate of the DataLad, since PIP then opens the
  way to a RCs for any later releases to be installed
- `simple_with_archives`
  - issue warning if incoming_pipeline has Annexificator but no `annex` is given
- `crcns`
  - skip (but warn if relevant) records without xml
- do not crash while saving updated crawler's URL db to the file which is annexed.

# 0.3 (Feb 06, 2019) -- Happy New Year

Primarily a variety of fixes

- `crcns` crawler now uses new datacite interface
- `openfmri` crawler uses legacy.openfmri.org
- `simple_with_archives`
  - by default now also match pure .gz files to be downloaded
  - `archives_re` option provides regex for archives files (so `.gz`
    could be added if needed)
  - will now run with `tarballs=False`
  - `add_annex_to_incoming_pipeline` to state either to add `annex`
    to the incoming pipeline
- new `stanford_lib` pipeline
- aggregation of metadata explicitly invokes incremental mode
- tests
  - variety of tests lost their `@known_failure_v6` and now tolerant
    to upcoming datalad 0.11.2

# 0.2 (May 17, 2018) -- The other Release

- All non-master branches in the pipelines now will initiate from master
  branch, not detached.  That should allow to inherit .gitattributes
  settings of the entire dataset

# 0.1 (May 11, 2018) -- The Release

- First release as a DataLad extension. Functionality remains identical
  to DataLad 0.10.0.rc2
