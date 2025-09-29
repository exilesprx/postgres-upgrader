import pytest
from docker_utils import backup_location


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


def test_parse_basic_compose(temp_compose_file):
    """Test basic compose file parsing"""
    data = backup_location(str(temp_compose_file))
    assert "/var/lib/postgresql/backups" in data
