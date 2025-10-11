"""
Tests for Docker Compose parsing functionality.
Tests the actual building blocks that the application uses.
"""

from unittest.mock import patch

import pytest

from postgres_upgrader import (
    DockerComposeConfig,
    parse_docker_compose,
)
from postgres_upgrader.compose_inspector import ServiceConfig, VolumeMount

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


class TestVolumeMount:
    """Test volume mount parsing functionality."""

    def test_volume_mount_parsing_other_type(self):
        """Test that non-volume mount types raise an exception."""
        volume_config = {
            "type": "bind",
            "source": "/host/path",
            "target": "/container/path",
        }

        volume = VolumeMount.from_string(volume_config)
        assert volume is None

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
        volume_mappings = {
            "database": {"name": "test_project_database"},
            "backups": {"name": "test_project_backups"},
        }
        volumes = [
            VolumeMount.from_string(config, volume_mappings)
            for config in volume_configs
        ]

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
        volume_mappings = {
            "database": {"name": "test_project_database"},
            "logs": {"name": "test_project_logs"},
        }
        volumes = [
            VolumeMount.from_string(config, volume_mappings)
            for config in volume_configs
        ]

        # Try to find non-existent volume
        missing_volume = next((v for v in volumes if v.name == "backups"), None)
        assert missing_volume is None

    def test_volume_access_empty_list(self):
        """Test accessing volumes from empty list."""
        volumes = []
        missing_volume = next((v for v in volumes if v.name == "backups"), None)
        assert missing_volume is None


class TestVolumeValidation:
    """Test volume validation for PostgreSQL upgrade operations."""

    def test_valid_volume_configuration(self):
        """Test that valid volume configuration passes validation."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/var/lib/postgresql/backups",
            raw="backups:/var/lib/postgresql/backups",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is True

    def test_same_volume_configuration(self):
        """Test that same volume for main and backup fails validation."""

        service = ServiceConfig(name="test")
        same_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="test_project_database",
        )
        service.select_volumes(same_vol, same_vol)

        assert service.is_configured_for_postgres_upgrade() is False

    def test_nested_path_configuration(self):
        """Test that backup volume inside main volume fails validation."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/var/lib/postgresql/data/backups",
            raw="backups:/var/lib/postgresql/data/backups",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is False

    def test_no_volumes_selected(self):
        """Test that no volumes selected fails validation."""

        service = ServiceConfig(name="test")

        assert service.is_configured_for_postgres_upgrade() is False

    def test_only_main_volume_selected(self):
        """Test that only main volume selected fails validation."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="test_project_database",
        )
        service.selected_main_volume = main_vol
        # Leave backup volume as None

        assert service.is_configured_for_postgres_upgrade() is False


class TestVolumeValidationEdgeCases:
    """Test advanced edge cases for volume validation."""

    def test_backup_volume_is_postgres_data_directory(self):
        """Test that using PostgreSQL data directory as backup raises exception."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/custom",
            raw="database:/var/lib/postgresql/custom",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/var/lib/postgresql/data",  # This is the dangerous path
            raw="backups:/var/lib/postgresql/data",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # Should raise exception when trying to validate
        with pytest.raises(
            Exception,
            match="You cannot use the default PostgreSQL data directory as a backup location",
        ):
            service.is_configured_for_postgres_upgrade()

    def test_backup_volume_exact_match_main_volume_path(self):
        """Test that backup volume with exact same path as main volume fails."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/custom/data",
            raw="database:/custom/data",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/custom/data",  # Exact same path, different volume name
            raw="backups:/custom/data",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is False

    def test_paths_with_trailing_slashes(self):
        """Test volume validation handles trailing slashes correctly."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data/",
            raw="database:/var/lib/postgresql/data/",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/var/lib/postgresql/backups/",
            raw="backups:/var/lib/postgresql/backups/",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is True

    def test_nested_path_with_trailing_slashes(self):
        """Test nested path detection works with trailing slashes."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data/",
            raw="database:/var/lib/postgresql/data/",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/var/lib/postgresql/data/backups/",
            raw="backups:/var/lib/postgresql/data/backups/",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is False

    def test_backup_volume_parent_of_main_volume(self):
        """Test that backup volume as parent of main volume is allowed."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data/db",
            raw="database:/var/lib/postgresql/data/db",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/var/lib/postgresql",
            raw="backups:/var/lib/postgresql",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # Parent directory as backup should be valid (not nested inside main)
        assert service.is_configured_for_postgres_upgrade() is True

    def test_volumes_with_none_paths(self):
        """Test volume validation handles None paths gracefully."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path=None,
            raw="database",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path=None,
            raw="backups",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # None paths become empty strings, which are equal -> invalid
        assert service.is_configured_for_postgres_upgrade() is False

    def test_mixed_none_and_valid_paths(self):
        """Test validation with one None path and one valid path."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path=None,
            raw="backups",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is True

    def test_empty_string_paths(self):
        """Test volume validation handles empty string paths."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="",
            raw="database",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="",
            raw="backups",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # Empty paths are equal after normalization -> invalid
        assert service.is_configured_for_postgres_upgrade() is False

    def test_single_character_paths(self):
        """Test volume validation with single character paths."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/",
            raw="database:/",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/b",
            raw="backups:/b",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # Root path "/" becomes "" after rstrip, so "/b" starts with "" + "/" = "/" -> nested -> invalid
        assert service.is_configured_for_postgres_upgrade() is False

    def test_complex_nested_paths(self):
        """Test complex nested path scenarios."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/app/postgres/data",
            raw="database:/app/postgres/data",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/app/postgres/data/subdir/backups",
            raw="backups:/app/postgres/data/subdir/backups",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is False

    def test_similar_but_not_nested_paths(self):
        """Test paths that look similar but are not nested."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/var/lib/postgresql/data_backup",
            raw="backups:/var/lib/postgresql/data_backup",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # data_backup is not nested inside data
        assert service.is_configured_for_postgres_upgrade() is True

    def test_unicode_paths(self):
        """Test volume validation with Unicode characters in paths."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/données/postgresql",
            raw="database:/données/postgresql",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/sauvegarde/données",
            raw="backups:/sauvegarde/données",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is True

    def test_windows_style_paths(self):
        """Test volume validation with Windows-style paths (for completeness)."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="C:\\data\\postgresql",
            raw="database:C:\\data\\postgresql",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="D:\\backups\\postgresql",
            raw="backups:D:\\backups\\postgresql",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is True

    def test_very_long_paths(self):
        """Test volume validation with very long paths."""

        service = ServiceConfig(name="test")
        long_path = "/very/long/path/that/goes/on/and/on/and/on/postgresql/data"
        main_vol = VolumeMount(
            name="database",
            path=long_path,
            raw=f"database:{long_path}",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/completely/different/very/long/backup/path/structure",
            raw="backups:/completely/different/very/long/backup/path/structure",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        assert service.is_configured_for_postgres_upgrade() is True

    def test_root_filesystem_edge_case(self):
        """Test edge case with root filesystem paths that should be valid."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/data",
            raw="database:/data",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/backup",
            raw="backups:/backup",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # /data and /backup are siblings under root -> valid
        assert service.is_configured_for_postgres_upgrade() is True

    def test_path_normalization_edge_cases(self):
        """Test that path normalization handles edge cases correctly."""

        service = ServiceConfig(name="test")
        main_vol = VolumeMount(
            name="database",
            path="/app/data////",
            raw="database:/app/data////",
            resolved_name="test_project_database",
        )
        backup_vol = VolumeMount(
            name="backups",
            path="/app/backup///",
            raw="backups:/app/backup///",
            resolved_name="test_project_backups",
        )
        service.select_volumes(main_vol, backup_vol)

        # Multiple trailing slashes should be normalized correctly
        assert service.is_configured_for_postgres_upgrade() is True

    def test_volume_name_vs_path_different_logic(self):
        """Test that volume name comparison and path comparison are handled separately."""

        service = ServiceConfig(name="test")
        # Same name = invalid regardless of path
        same_vol = VolumeMount(
            name="database",
            path="/var/lib/postgresql/data",
            raw="database:/var/lib/postgresql/data",
            resolved_name="test_project_database",
        )
        different_path_same_name = VolumeMount(
            name="database",  # Same name!
            path="/completely/different/path",
            raw="database:/completely/different/path",
            resolved_name="test_project_database",
        )
        service.select_volumes(same_vol, different_path_same_name)

        # Should fail due to same volume name, not path
        assert service.is_configured_for_postgres_upgrade() is False


class TestDockerComposeConfigMethods:
    """Test DockerComposeConfig utility methods."""

    def setup_method(self):
        """Set up test fixtures."""

        # Create a realistic Docker Compose config for testing
        postgres_service = ServiceConfig(
            name="postgres",
            volumes=[
                VolumeMount(
                    name="postgres_data",
                    path="/var/lib/postgresql/data",
                    raw="postgres_data:/var/lib/postgresql/data",
                    resolved_name="test_project_postgres_data",
                ),
                VolumeMount(
                    name="postgres_backups",
                    path="/tmp/postgresql/backups",
                    raw="postgres_backups:/tmp/postgresql/backups",
                    resolved_name="test_project_postgres_backups",
                ),
            ],
        )

        # Add environment variables for PostgreSQL
        postgres_service.environment = {
            "POSTGRES_USER": "testuser",
            "POSTGRES_DB": "testdb",
            "POSTGRES_PASSWORD": "testpass",
        }

        redis_service = ServiceConfig(
            name="redis",
            volumes=[
                VolumeMount(
                    name="redis_data",
                    path="/data",
                    raw="redis_data:/data",
                    resolved_name="test_project_redis_data",
                ),
            ],
        )

        self.compose_config = DockerComposeConfig(
            name="test_project",
            services={"postgres": postgres_service, "redis": redis_service},
        )

    def test_get_service_exists(self):
        """Test get_service returns correct service when it exists."""
        service = self.compose_config.get_service("postgres")
        assert service is not None
        assert service.name == "postgres"
        assert len(service.volumes) == 2

    def test_get_service_not_exists(self):
        """Test get_service returns None when service doesn't exist."""
        service = self.compose_config.get_service("nonexistent")
        assert service is None

    def test_get_volumes_existing_service(self):
        """Test get_volumes returns volumes for existing service."""
        volumes = self.compose_config.get_volumes("postgres")
        assert len(volumes) == 2
        assert volumes[0].name == "postgres_data"
        assert volumes[1].name == "postgres_backups"

    def test_get_volumes_nonexistent_service(self):
        """Test get_volumes returns empty list for nonexistent service."""
        volumes = self.compose_config.get_volumes("nonexistent")
        assert volumes == []

    def test_get_postgres_user_with_env_var(self):
        """Test get_postgres_user returns value from environment variable."""
        user = self.compose_config.get_postgres_user("postgres")
        assert user == "testuser"

    def test_get_postgres_user_no_env_var(self):
        """Test get_postgres_user returns None when no env var set."""
        user = self.compose_config.get_postgres_user("redis")
        assert user is None

    def test_get_postgres_user_nonexistent_service(self):
        """Test get_postgres_user returns None for nonexistent service."""
        user = self.compose_config.get_postgres_user("nonexistent")
        assert user is None

    def test_get_postgres_db_with_env_var(self):
        """Test get_postgres_db returns value from environment variable."""
        db = self.compose_config.get_postgres_db("postgres")
        assert db == "testdb"

    def test_get_postgres_db_no_env_var(self):
        """Test get_postgres_db returns None when no env var set."""
        db = self.compose_config.get_postgres_db("redis")
        assert db is None

    def test_get_postgres_db_nonexistent_service(self):
        """Test get_postgres_db returns None for nonexistent service."""
        db = self.compose_config.get_postgres_db("nonexistent")
        assert db is None
