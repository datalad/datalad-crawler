import datalad.tests.utils_pytest
from datalad.conftest import setup_package  # autoused fixture
import pytest

_datalad_default_branch = datalad.tests.utils_pytest.DEFAULT_BRANCH

@pytest.fixture(autouse=True, scope="session")
def setup_branch():
    # Q&D workaround for not messing for now with datalad specifying default
    # branch to be not master
    datalad.tests.utils_pytest.DEFAULT_BRANCH = 'master'
    yield
    datalad.tests.utils_pytest.DEFAULT_BRANCH = _datalad_default_branch
