     ____            _             _                   _ 
    |  _ \    __ _  | |_    __ _  | |       __ _    __| |
    | | | |  / _` | | __|  / _` | | |      / _` |  / _` |
    | |_| | | (_| | | |_  | (_| | | |___  | (_| | | (_| |
    |____/   \__,_|  \__|  \__,_| |_____|  \__,_|  \__,_|
                                               Crawler

This is a high level and scarce summary of the changes between releases.  We
would recommend to consult log of the [DataLad git
repository](http://github.com/datalad/datalad-crawler) for more details.

## 0.4.4 (Nov 20, 2019) -- ... despite some mocking

- ENH: `s3_simple` pipeline got additional option `drop_immediately` to
  drop files immediately upon having them annexed
- RF: `mock` is explicitly listed as a dependency for testing since DataLad
  0.12.x will be PY3 only and could use built-in `unittest.mock`

## 0.4.3 (Oct 30, 2019) -- ... and help each other

- MNT: More changes for compatibility with developmental DataLad (#62)

## 0.4.2 (Oct 30, 2019) -- Friends should stick together ...

- BF: Prevent sorting error on missing attribute (#45)
- BF: enclose "if else" into () since it has lower precedence than + (#43)
- MNT: Adjust imports for compatibility with developmental DataLad (#53)
- MNT: Update save() call for compatibility with new save (#42)

## 0.4.1 (Jun 20, 2019) -- Let us all stay friends

- Compatibility layer with 0.12 series of DataLad changing API
  (no backend option for `create`)

## 0.4 (Mar 14, 2019) -- There is more to life than a Pi

Primarily a variety of fixes and small enhancements. The only notable
change is stripping away testing/support of git-annex direct mode.

- do not depend on a release candidate of the DataLad, since PIP then opens the
  way to a RCs for any later releases to be installed
- `simple_with_archives`
  - issue warning if incoming_pipeline has Annexificator but no `annex` is given
- `crcns`
  - skip (but warn if relevant) records without xml
- do not crash while saving updated crawler's URL db to the file which is annexed.

## 0.3 (Feb 06, 2019) -- Happy New Year

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
  - variety of tests lost their `@known_failure_v6` and now tollerant
    to upcoming datalad 0.11.2

## 0.2 (May 17, 2018) -- The other Release

- All non-master branches in the pipelines now will initiate from master
  branch, not detached.  That should allow to inherit .gitattributes
  settings of the entire dataset

## 0.1 (May 11, 2018) -- The Release

- First release as a DataLad extension. Functionality remains identical
  to DataLad 0.10.0.rc2
