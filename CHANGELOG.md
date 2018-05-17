     ____            _             _                   _ 
    |  _ \    __ _  | |_    __ _  | |       __ _    __| |
    | | | |  / _` | | __|  / _` | | |      / _` |  / _` |
    | |_| | | (_| | | |_  | (_| | | |___  | (_| | | (_| |
    |____/   \__,_|  \__|  \__,_| |_____|  \__,_|  \__,_|
                                               Crawler

This is a high level and scarce summary of the changes between releases.  We
would recommend to consult log of the [DataLad git
repository](http://github.com/datalad/datalad-crawler) for more details.

## 02 (May 17, 2018) -- The other Release

- All non-master branches in the pipelines now will initiate from master
  branch, not detached.  That should allow to inherit .gitattributes
  settings of the entire dataset

## 0.1 (May 11, 2018) -- The Release

- First release as a DataLad extension. Functionality remains identical
  to DataLad 0.10.0.rc2
