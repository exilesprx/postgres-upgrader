"""
Tests for Docker backup functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
from postgres_upgrader import DockerManager, ServiceConfig, VolumeMount


class TestDockerManager:
    """Test Docker Manager functionality."""

    def test_docker_manager_create_postgres_backup(self):
        """Test that DockerManager.create_postgres_backup accepts correct parameters."""
        # This test verifies the function signature without Docker dependencies

        # Create service config with selections using the new data classes
        service_config = ServiceConfig(
            name="postgres",
            volumes=[
                VolumeMount(
                    name="database",
                    path="/var/lib/postgresql/data",
                    raw="database:/var/lib/postgresql/data",
                    resolved_name="test_database",
                ),
                VolumeMount(
                    name="backups",
                    path="/var/lib/postgresql/backups",
                    raw="backups:/var/lib/postgresql/backups",
                    resolved_name="test_backups",
                ),
            ],
        )
        # Set selections to simulate user choice
        service_config.selected_main_volume = service_config.volumes[0]
        service_config.selected_backup_volume = service_config.volumes[1]

        # Mock Docker to test the function structure
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_client.containers.list.return_value = []  # No containers found

            # Should raise exception when no containers found - using new API
            with DockerManager(
                service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(Exception, match="No containers found"):
                    docker_mgr.create_postgres_backup()

    def test_docker_manager_constructor_parameters(self):
        """Test that DockerManager constructor stores parameters correctly."""
        service_config = ServiceConfig(name="test")

        with patch("postgres_upgrader.docker.docker.from_env"):
            with DockerManager(
                service_config, "postgres", "myuser", "mydb"
            ) as docker_mgr:
                assert docker_mgr.service_config == service_config
                assert docker_mgr.container_user == "postgres"
                assert docker_mgr.database_user == "myuser"
                assert docker_mgr.database_name == "mydb"

    def test_docker_manager_requires_all_parameters(self):
        """Test that DockerManager constructor requires all parameters."""
        service_config = ServiceConfig(name="test")

        # Should raise TypeError if parameters are missing
        with pytest.raises(TypeError):
            DockerManager(service_config)  # Missing required parameters

    def test_docker_manager_methods_use_instance_variables(self):
        """Test that methods use instance variables instead of parameters."""
        service_config = ServiceConfig(
            name="postgres",
            volumes=[
                VolumeMount(
                    name="database",
                    path="/var/lib/postgresql/data",
                    raw="database:/var/lib/postgresql/data",
                    resolved_name="test_database",
                ),
            ],
        )
        service_config.selected_main_volume = service_config.volumes[0]

        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock a container that uses the instance variables
            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_container.exec_run.return_value = MagicMock(
                exit_code=0, output=b"success"
            )
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                service_config, "testuser", "dbuser", "testdb"
            ) as docker_mgr:
                # Methods should use instance variables, not require parameters
                try:
                    docker_mgr.update_collation_version()
                    # If it doesn't raise TypeError, the method is using instance vars correctly
                except Exception as e:
                    # Any other exception is fine, but TypeError would indicate missing params
                    assert not isinstance(e, TypeError), (
                        "Method should use instance variables"
                    )

    def test_docker_manager_error_propagation(self):
        """Test that errors are properly propagated with new constructor."""
        service_config = ServiceConfig(
            name="postgres",
            volumes=[
                VolumeMount(
                    name="database",
                    path="/var/lib/postgresql/data",
                    raw="database:/var/lib/postgresql/data",
                    resolved_name="test_database",
                ),
            ],
        )
        service_config.selected_main_volume = service_config.volumes[0]
        
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            # Simulate Docker connection error
            mock_docker.side_effect = Exception("Docker connection failed")
            
            # Constructor should handle Docker connection properly
            with pytest.raises(Exception, match="Docker connection failed"):
                with DockerManager(service_config, "postgres", "testuser", "testdb"):
                    pass  # Should fail on context manager entry
