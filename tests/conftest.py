import os
from pathlib import Path

import pytest

TEST_DIR = Path(__file__).parent


@pytest.fixture
def change_test_dir(request):
    os.chdir(request.fspath.dirname)
    yield
    os.chdir(request.config.invocation_dir)
