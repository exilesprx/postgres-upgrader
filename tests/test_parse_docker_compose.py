"""
Tests for Docker Compose parsing functionality.
Tests the actual building blocks that the application uses.
"""

import tempfile
import os
import pytest
from postgres_updater import (
    get_services,
    get_volumes,
    parse_docker_compose,
    extract_location,
)


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

        assert "services" in result
        assert "postgres" in result["services"]
        assert "nginx" in result["services"]
        assert "volumes" in result


class TestGetServices:
    """Test service extraction from Docker Compose files."""

    def test_get_services(self, compose_file):
        """Test getting list of services."""
        services = get_services(compose_file)

        assert isinstance(services, list)
        assert "postgres" in services
        assert "nginx" in services
        assert len(services) == 2


class TestGetVolumes:
    """Test volume extraction for specific services."""

    def test_get_volumes_postgres(self, compose_file):
        """Test getting volumes for postgres service."""
        volumes = get_volumes(compose_file, "postgres")

        assert isinstance(volumes, list)
        assert len(volumes) == 2
        assert "database:/var/lib/postgresql/data" in volumes
        assert "backups:/var/lib/postresql/backups" in volumes

    def test_get_volumes_nginx(self, compose_file):
        """Test getting volumes for nginx service."""
        volumes = get_volumes(compose_file, "nginx")

        assert isinstance(volumes, list)
        assert len(volumes) == 2
        assert "./nginx.conf:/etc/nginx/nginx.conf" in volumes
        assert "logs:/var/log/nginx" in volumes

    def test_get_volumes_nonexistent_service(self, compose_file):
        """Test getting volumes for non-existent service."""
        volumes = get_volumes(compose_file, "nonexistent")

        assert volumes == []


class TestExtractLocation:
    """Test location extraction from volume strings."""

    def test_extract_location_found(self):
        """Test extracting location when pattern is found."""
        volumes = [
            "database:/var/lib/postgresql/data",
            "backups:/var/lib/postresql/backups",
        ]

        result = extract_location("backups", volumes)
        assert result == "/var/lib/postresql/backups"

    def test_extract_location_not_found(self):
        """Test extracting location when pattern is not found."""
        volumes = ["database:/var/lib/postgresql/data", "logs:/var/log/nginx"]

        result = extract_location("backups", volumes)
        assert result is None

    def test_extract_location_empty_volumes(self):
        """Test extracting location from empty volume list."""
        result = extract_location("backups", [])
        assert result is None
