from datalad.utils import chpwd

from datalad.api import (
    crawl,
    crawl_init,
    create,
)
try:
    from datalad.support.github_ import _get_github_cred
except ImportError:
    # might be dated which has not merged
    # https://github.com/datalad/datalad/pull/4400 yet
    from datalad.downloaders.credentials import UserPassword
    def _get_github_cred():
        """Trimmed down helper"""
        return UserPassword("github", "does not matter")

from datalad.tests.utils_pytest import (
    assert_false,
    assert_greater,
    skip_if_no_network,
    with_tempfile,
)
import pytest


@skip_if_no_network
@with_tempfile
def test_crawl(tempd=None):
    if not _get_github_cred().is_known:
        pytest.skip("no github credential")
    ds = create(tempd)
    with chpwd(tempd):
        crawl_init(
            template='gh', save=True,
            args={'org': 'datalad-collection-1', 'include': 'kaggle'}
        )
        crawl()
    subdss = ds.subdatasets(fulfilled=True, result_xfm='datasets')
    assert all('kaggle' in d.path for d in subdss)
    assert_greater(len(subdss), 1)
    assert_false(ds.repo.dirty)
