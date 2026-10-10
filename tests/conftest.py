import pytest
from database import Gateway

@pytest.fixture
def gateway(tmp_path):
    return Gateway(tmp_path / "audit.sqlite3")
