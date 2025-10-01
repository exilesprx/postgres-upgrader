"""
Tests for Docker Compose parsing functionality.
Tests the actual building blocks that the application uses.
"""

import pytest
from postgres_upgrader import (
    parse_docker_compose,
    DockerComposeConfig,
)
from postgres_upgrader.compose_inspector import VolumeMount


class TestParseDockerCompose:
    """Test Docker Compose parsing using real docker compose config."""

    def test_parse_docker_compose(self):
        """Test parsing Docker Compose using docker compose config."""
        compose_data = parse_docker_compose()

        assert isinstance(compose_data, DockerComposeConfig)
        assert "postgres" in compose_data.services
        assert "nginx" in compose_data.services

import tempfile
import os
import pytest
from postgres_upgrader import (
    parse_docker_compose,
    DockerComposeConfig,
)
from postgres_upgrader.compose_inspector import VolumeMount


class TestParseDockerCompose:
    """Test Docker Compose YAML parsing."""

    def test_parse_docker_compose(self):
        """Test that Docker Compose config is parsed correctly."""
        result = parse_docker_compose()

        assert isinstance(result, DockerComposeConfig)
        assert "postgres" in result.services
        assert "nginx" in result.services
        assert result.services["postgres"].name == "postgres"
        assert result.services["nginx"].name == "nginx"


class TestGetServices:
    """Test service retrieval from parsed compose data."""

    def test_get_services(self):
        """Test getting services from parsed compose data."""
        compose_data = parse_docker_compose()
        services = compose_data.services

        assert isinstance(services, dict)
        assert "postgres" in services
        assert "nginx" in services


class TestGetVolumes:
    """Test volume extraction for specific services."""

    def test_get_volumes_postgres(self):
        """Test getting volumes for postgres service."""
        compose_data = parse_docker_compose()
        volumes = compose_data.get_volumes("postgres")

        assert isinstance(volumes, list)
        assert len(volumes) == 2
        
        volume_raws = [v.raw for v in volumes]
        assert "database:/var/lib/postgresql/data" in volume_raws
        assert "backups:/var/lib/postgresql/backups" in volume_raws

    def test_get_volumes_nginx(self):
        """Test getting volumes for nginx service."""
        compose_data = parse_docker_compose()
        volumes = compose_data.get_volumes("nginx")

        assert isinstance(volumes, list)
        # Nginx service has no volumes in the real docker-compose.yml
        assert len(volumes) == 0

    def test_get_volumes_nonexistent_service(self):
        """Test getting volumes for non-existent service."""
        compose_data = parse_docker_compose()
        volumes = compose_data.get_volumes("nonexistent")

        assert volumes == []


class TestVolumeAccess:
    """Test accessing volume information directly from VolumeMount objects."""

    def test_volume_access_by_name(self):
        """Test finding volumes by name and accessing their properties."""
        volume_configs = [
            {"type": "volume", "source": "database", "target": "/var/lib/postgresql/data", "volume": {}},
            {"type": "volume", "source": "backups", "target": "/var/lib/postgresql/backups", "volume": {}},
        ]
        volumes = [VolumeMount.from_string(config) for config in volume_configs]
        
        # Find backup volume by name
        backup_volume = next((v for v in volumes if v.name == "backups"), None)
        assert backup_volume is not None
        assert backup_volume.path == "/var/lib/postgresql/backups"
        assert backup_volume.raw == "backups:/var/lib/postgresql/backups"

    def test_volume_access_name_not_found(self):
        """Test when volume name is not found."""
        volume_configs = [
            {"type": "volume", "source": "database", "target": "/var/lib/postgresql/data", "volume": {}},
            {"type": "volume", "source": "logs", "target": "/var/log/nginx", "volume": {}},
        ]
        volumes = [VolumeMount.from_string(config) for config in volume_configs]
        
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
        """Test parsing volume mount config dict with valid format."""
        volume_config = {
            "type": "volume",
            "source": "database",
            "target": "/var/lib/postgresql/data",
            "volume": {}
        }
        volume_mappings = {
            "database": {"name": "postgres-updater_database"}
        }
        
        result = VolumeMount.from_string(volume_config, volume_mappings)
        
        expected = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="postgres-updater_database"
        )
        
        assert result == expected

    def test_volume_mount_parsing_other_type(self):
        """Test parsing volume mount config dict with non-volume type."""
        volume_config = {
            "type": "bind",
            "source": "/host/path",
            "target": "/container/path"
        }
        
        result = VolumeMount.from_string(volume_config)
        
        expected = VolumeMount(
            name=None,
            path="/container/path",
            raw="unknown:/container/path",
            resolved_name=None
        )
        
        assert result == expected
