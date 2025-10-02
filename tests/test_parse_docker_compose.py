"""
Tests for Docker Compose parsing functionality.
Tests the actual building blocks that the application uses.
"""

from unittest.mock import patch
from postgres_upgrader import (
    parse_docker_compose,
    DockerComposeConfig,
)
from postgres_upgrader.compose_inspector import VolumeMount

# Mock docker compose config output
MOCK_DOCKER_COMPOSE_CONFIG = """
name: postgres-updater
services:
  nginx:
    image: nginx:latest
    networks:
      default: null
    ports:
    - mode: ingress
      target: 8000
      published: "80"
      protocol: tcp
  postgres:
    environment:
      POSTGRES_DB: testing
      POSTGRES_PASSWORD: testing
      POSTGRES_USER: tester
    image: postgres:17.0
    networks:
      default: null
    volumes:
    - type: volume
      source: database
      target: /var/lib/postgresql/data
      volume: {}
    - type: volume
      source: backups
      target: /var/lib/postgresql/backups
      volume: {}
networks:
  default:
    name: postgres-updater_default
volumes:
  backups:
    name: postgres-updater_backups
  database:
    name: postgres-updater_database
"""


class TestParseDockerCompose:
    """Test Docker Compose parsing using mocked docker compose config."""

    @patch("postgres_upgrader.compose_inspector.subprocess.run")
    def test_parse_docker_compose(self, mock_run):
        """Test parsing Docker Compose using mocked docker compose config."""
        # Mock the subprocess call to return our test data
        mock_run.return_value.stdout = MOCK_DOCKER_COMPOSE_CONFIG
        mock_run.return_value.returncode = 0

        compose_data = parse_docker_compose()

        assert isinstance(compose_data, DockerComposeConfig)
        assert "postgres" in compose_data.services
        assert "nginx" in compose_data.services


class TestGetServices:
    """Test service retrieval from parsed compose data."""

    @patch("postgres_upgrader.compose_inspector.subprocess.run")
    def test_get_services(self, mock_run):
        """Test getting services from parsed compose data."""
        # Mock the subprocess call
        mock_run.return_value.stdout = MOCK_DOCKER_COMPOSE_CONFIG
        mock_run.return_value.returncode = 0

        compose_data = parse_docker_compose()
        services = compose_data.services

        assert isinstance(services, dict)
        assert "postgres" in services
        assert "nginx" in services


class TestGetVolumes:
    """Test volume extraction for specific services."""

    @patch("postgres_upgrader.compose_inspector.subprocess.run")
    def test_get_volumes_postgres(self, mock_run):
        """Test getting volumes for postgres service."""
        # Mock the subprocess call
        mock_run.return_value.stdout = MOCK_DOCKER_COMPOSE_CONFIG
        mock_run.return_value.returncode = 0

        compose_data = parse_docker_compose()
        volumes = compose_data.get_volumes("postgres")

        assert isinstance(volumes, list)
        assert len(volumes) == 2

        volume_raws = [v.raw for v in volumes]
        assert "database:/var/lib/postgresql/data" in volume_raws
        assert "backups:/var/lib/postgresql/backups" in volume_raws

    @patch("postgres_upgrader.compose_inspector.subprocess.run")
    def test_get_volumes_nginx(self, mock_run):
        """Test getting volumes for nginx service."""
        # Mock the subprocess call
        mock_run.return_value.stdout = MOCK_DOCKER_COMPOSE_CONFIG
        mock_run.return_value.returncode = 0

        compose_data = parse_docker_compose()
        volumes = compose_data.get_volumes("nginx")

        assert isinstance(volumes, list)
        # Nginx service has no volumes in the mocked docker-compose.yml
        assert len(volumes) == 0

    @patch("postgres_upgrader.compose_inspector.subprocess.run")
    def test_get_volumes_nonexistent_service(self, mock_run):
        """Test getting volumes for non-existent service."""
        # Mock the subprocess call
        mock_run.return_value.stdout = MOCK_DOCKER_COMPOSE_CONFIG
        mock_run.return_value.returncode = 0

        compose_data = parse_docker_compose()
        volumes = compose_data.get_volumes("nonexistent")

        assert volumes == []


class TestVolumeAccess:
    """Test accessing volume information directly from VolumeMount objects."""

    def test_volume_access_by_name(self):
        """Test finding volumes by name and accessing their properties."""
        volume_configs = [
            {
                "type": "volume",
                "source": "database",
                "target": "/var/lib/postgresql/data",
                "volume": {},
            },
            {
                "type": "volume",
                "source": "backups",
                "target": "/var/lib/postgresql/backups",
                "volume": {},
            },
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
            {
                "type": "volume",
                "source": "database",
                "target": "/var/lib/postgresql/data",
                "volume": {},
            },
            {
                "type": "volume",
                "source": "logs",
                "target": "/var/log/nginx",
                "volume": {},
            },
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
            "volume": {},
        }
        volume_mappings = {"database": {"name": "postgres-updater_database"}}

        result = VolumeMount.from_string(volume_config, volume_mappings)

        expected = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="postgres-updater_database",
        )

        assert result == expected

    def test_volume_mount_parsing_other_type(self):
        """Test parsing volume mount config dict with non-volume type."""
        volume_config = {
            "type": "bind",
            "source": "/host/path",
            "target": "/container/path",
        }

        result = VolumeMount.from_string(volume_config)

        expected = VolumeMount(
            name=None,
            path="/container/path",
            raw="unknown:/container/path",
            resolved_name=None,
        )

        assert result == expected


class TestVolumeValidation:
    """Test volume validation for PostgreSQL upgrade operations."""

    def test_valid_volume_configuration(self):
        """Test that valid volume configuration passes validation."""
        from postgres_upgrader.compose_inspector import ServiceConfig
        
        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database", 
            path="/var/lib/postgresql/data", 
            raw="database:/var/lib/postgresql/data"
        )
        backup_vol = VolumeMount(
            name="backups", 
            path="/var/lib/postgresql/backups", 
            raw="backups:/var/lib/postgresql/backups"
        )
        service.select_volumes(main_vol, backup_vol)
        
        assert service.is_configured_for_postgres_upgrade() is True

    def test_same_volume_configuration(self):
        """Test that same volume for main and backup fails validation."""
        from postgres_upgrader.compose_inspector import ServiceConfig
        
        service = ServiceConfig(name="test")
        same_vol = VolumeMount(
            name="database", 
            path="/var/lib/postgresql/data", 
            raw="database:/var/lib/postgresql/data"
        )
        service.select_volumes(same_vol, same_vol)
        
        assert service.is_configured_for_postgres_upgrade() is False

    def test_nested_path_configuration(self):
        """Test that backup volume inside main volume fails validation."""
        from postgres_upgrader.compose_inspector import ServiceConfig
        
        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database", 
            path="/var/lib/postgresql/data", 
            raw="database:/var/lib/postgresql/data"
        )
        backup_vol = VolumeMount(
            name="backups", 
            path="/var/lib/postgresql/data/backups", 
            raw="backups:/var/lib/postgresql/data/backups"
        )
        service.select_volumes(main_vol, backup_vol)
        
        assert service.is_configured_for_postgres_upgrade() is False

    def test_no_volumes_selected(self):
        """Test that no volumes selected fails validation."""
        from postgres_upgrader.compose_inspector import ServiceConfig
        
        service = ServiceConfig(name="test")
        
        assert service.is_configured_for_postgres_upgrade() is False

    def test_only_main_volume_selected(self):
        """Test that only main volume selected fails validation."""
        from postgres_upgrader.compose_inspector import ServiceConfig
        
        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database", 
            path="/var/lib/postgresql/data", 
            raw="database:/var/lib/postgresql/data"
        )
        service.selected_main_volume = main_vol
        # Leave backup volume as None
        
        assert service.is_configured_for_postgres_upgrade() is False
