"""
Tests for Docker backup functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
from postgres_upgrader import DockerManager, ServiceVolumeConfig, VolumeInfo


class TestDockerManager:
    """Test Docker Manager functionality."""

    def test_docker_manager_create_postgres_backup(self):
        """Test that DockerManager.create_postgres_backup accepts correct parameters."""
        # This test verifies the function signature without Docker dependencies

        # Create service config using the new data classes
        service_config = ServiceVolumeConfig(
            name="postgres",
            main_volume=VolumeInfo(name="database", dir="/var/lib/postgresql/data"),
            backup_volume=VolumeInfo(name="backups", dir="/var/lib/postgresql/backups"),
        )

        # Mock Docker to test the function structure
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_client.containers.list.return_value = []  # No containers found

            # Should raise exception when no containers found - using new API
            with DockerManager(service_config=service_config) as docker_mgr:
                with pytest.raises(Exception, match="No containers found"):
                    docker_mgr.create_postgres_backup("testuser", "testdb")
