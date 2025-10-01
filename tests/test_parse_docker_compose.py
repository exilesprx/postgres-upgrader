"""
Tests for Docker Compose parsing functionality.
Tests the actual building blocks that the application uses.
"""

import tempfile
import os
import pytest
from postgres_upgrader import (
    parse_docker_compose,
    DockerComposeConfig,
)
from postgres_upgrader.compose_inspector import VolumeMount


@pytest.fixture
def sample_compose_content():
    """Sample Docker Compose content for testing."""
    return """
version: '3.8'
services:
  postgres:
    image: postgres:13
    volumes:
      - database:/var/lib/postgresql/data
      - backups:/var/lib/postresql/backups
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password

  nginx:
    image: nginx:latest
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - logs:/var/log/nginx

volumes:
  database:
  backups:
  logs:
"""


@pytest.fixture
def compose_file(sample_compose_content):
    """Create a temporary docker-compose.yml file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write(sample_compose_content)
        f.flush()
        yield f.name
    os.unlink(f.name)


class TestParseDockerCompose:
    """Test Docker Compose YAML parsing."""

    def test_parse_docker_compose(self, compose_file):
        """Test that Docker Compose YAML is parsed correctly."""
        result = parse_docker_compose(compose_file)

        assert isinstance(result, DockerComposeConfig)
        assert "postgres" in result.services
        assert "nginx" in result.services
        assert result.services["postgres"].name == "postgres"
        assert result.services["nginx"].name == "nginx"


class TestGetServices:
    """Test service extraction from Docker Compose files."""

    def test_get_services(self, compose_file):
        """Test getting services dictionary."""
        compose_data = parse_docker_compose(compose_file)
        services = compose_data.services

        assert isinstance(services, dict)
        assert "postgres" in services
        assert "nginx" in services
        assert len(services) == 2


class TestGetVolumes:
    """Test volume extraction for specific services."""

    def test_get_volumes_postgres(self, compose_file):
        """Test getting volumes for postgres service."""
        compose_data = parse_docker_compose(compose_file)
        volumes = compose_data.get_volumes("postgres")

        assert isinstance(volumes, list)
        assert len(volumes) == 2
        
        volume_raws = [v.raw for v in volumes]
        assert "database:/var/lib/postgresql/data" in volume_raws
        assert "backups:/var/lib/postresql/backups" in volume_raws

    def test_get_volumes_nginx(self, compose_file):
        """Test getting volumes for nginx service."""
        compose_data = parse_docker_compose(compose_file)
        volumes = compose_data.get_volumes("nginx")

        assert isinstance(volumes, list)
        assert len(volumes) == 2
        
        volume_raws = [v.raw for v in volumes]
        assert "./nginx.conf:/etc/nginx/nginx.conf" in volume_raws
        assert "logs:/var/log/nginx" in volume_raws

    def test_get_volumes_nonexistent_service(self, compose_file):
        """Test getting volumes for non-existent service."""
        compose_data = parse_docker_compose(compose_file)
        volumes = compose_data.get_volumes("nonexistent")

        assert volumes == []


class TestVolumeAccess:
    """Test accessing volume information directly from VolumeMount objects."""

    def test_volume_access_by_name(self):
        """Test finding volumes by name and accessing their properties."""
        volumes = [
            VolumeMount.from_string("database:/var/lib/postgresql/data"),
            VolumeMount.from_string("backups:/var/lib/postgresql/backups"),
        ]
        
        # Find backup volume by name
        backup_volume = next((v for v in volumes if v.name == "backups"), None)
        assert backup_volume is not None
        assert backup_volume.path == "/var/lib/postgresql/backups"
        assert backup_volume.raw == "backups:/var/lib/postgresql/backups"

    def test_volume_access_name_not_found(self):
        """Test when volume name is not found."""
        volumes = [
            VolumeMount.from_string("database:/var/lib/postgresql/data"), 
            VolumeMount.from_string("logs:/var/log/nginx")
        ]
        
        # Try to find non-existent volume
        missing_volume = next((v for v in volumes if v.name == "backups"), None)
        assert missing_volume is None

    def test_volume_access_empty_list(self):
        """Test accessing volumes from empty list."""
        volumes = []
        missing_volume = next((v for v in volumes if v.name == "backups"), None)
        assert missing_volume is None


class TestVolumeMount:
    """Test volume mount parsing functionality."""

    def test_volume_mount_parsing_complete(self):
        """Test parsing volume mount strings with valid format."""
        volume_str = "database:/var/lib/postgresql/data"
        
        result = VolumeMount.from_string(volume_str)
        
        expected = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data"
        )
        
        assert result == expected

    def test_volume_mount_parsing_invalid_format(self):
        """Test parsing volume mount strings with invalid format."""
        volume_str = "invalid-format-no-colon"
        
        result = VolumeMount.from_string(volume_str)
        
        expected = VolumeMount(
            name=None,
            path=None,
            raw="invalid-format-no-colon"
        )
        
        assert result == expected
