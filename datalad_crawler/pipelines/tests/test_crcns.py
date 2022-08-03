# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##


from .test_utils import _test_smoke_pipelines
from ..crcns import pipeline, superdataset_pipeline
from ..crcns import get_metadata

from datalad.tests.utils_pytest import skip_if_no_network
from datalad.tests.utils_pytest import ok_startswith
from datalad.support.exceptions import AccessFailedError, AccessDeniedError

import pytest


@pytest.mark.parametrize("func,args", [
    (pipeline, ['bogus', "bogusgroup"]),
    (superdataset_pipeline, []),
])
def test_smoke_pipelines(func, args):
    _test_smoke_pipelines(func, args)


@skip_if_no_network
def test_get_metadata():
    try:
        all_meta = get_metadata()
        # something broke somewhere and ATM returns no hits
        # Reported to CRCNS folks
        if len(all_meta) < 2:
            pytest.skip("Known to fail: wait for life to become better")
        assert len(all_meta) > 50  # so we have for all datasets
        # and each one of them should be a string (xml)
        assert all(x.startswith('<?xml') for x in all_meta.values())

        # but we could request one specific one
        aa1_meta = get_metadata('aa-1')
        ok_startswith(aa1_meta, '<?xml')
    except AccessFailedError as e:
        if str(e).startswith('Access to https://search.datacite.org') and \
                str(e).endswith('has failed: status code 502'):
            pytest.skip("Probably datacite.org blocked us once again")
    except AccessDeniedError:
        pytest.skip("datacite denied us and we asked, but waiting for an answer")
