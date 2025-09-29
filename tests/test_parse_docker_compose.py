import pytest
from postgres_updater import backup_location


@pytest.fixture
def temp_compose_file(tmp_path):
    """Create a temporary docker-compose.yml file"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("""
services:
  postgres:
    image: postgres:13
    volumes:
      - backups:/var/lib/postgresql/backups
      - database:/var/lib/postgresql/data
""")
    return compose_file


@pytest.fixture
def temp_compose_file_no_backups(tmp_path):
    """Create a temporary docker-compose.yml file without backup volumes"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text("""
services:
  postgres:
    image: postgres:13
    volumes:
      - database:/var/lib/postgresql/data
""")
    return compose_file


def test_parse_basic_compose(temp_compose_file):
    """Test basic compose file parsing"""
    data = backup_location(str(temp_compose_file))
    assert data is not None
    assert data == "/var/lib/postgresql/backups"


def test_parse_compose_no_backups(temp_compose_file_no_backups):
    """Test parsing when no backup volume is found"""
    data = backup_location(str(temp_compose_file_no_backups))
    assert data is None
