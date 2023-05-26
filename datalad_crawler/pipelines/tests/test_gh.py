from datalad.utils import chpwd

from datalad import cfg
from datalad.api import (
    crawl,
    crawl_init,
    create,
)
try:
    import github
except ImportError:
    github = None

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
    if not github:
        pytest.skip("no github package")
    # ATM tests completely overload HOME so TODO: do make it use credentials system
    if not cfg.get('hub.oauthtoken'):
        pytest.skip("no github credentials")
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
