from datalad.utils import chpwd

from datalad.api import (
    crawl,
    crawl_init,
    create,
)
try:
    from datalad.consts import GITHUB_LOGIN_URL
except ImportError:
    # might be dated which has not merged
    # https://github.com/datalad/datalad/pull/4400 yet
    GITHUB_LOGIN_URL = 'https://github.com/login'
from datalad.downloaders.tests.utils import get_test_providers

from datalad.tests.utils import (
    assert_false,
    assert_greater,
    skip_if_no_network,
    with_tempfile,
)


@skip_if_no_network
@with_tempfile
def test_crawl(tempd):
    get_test_providers(GITHUB_LOGIN_URL)
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