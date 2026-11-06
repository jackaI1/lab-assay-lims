import pytest

import factory_cell as fc


@pytest.fixture
def stage_path(tmp_path):
    return fc.build_cell(tmp_path / "cell")
