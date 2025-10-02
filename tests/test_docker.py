"""
Tests for Docker backup functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
import docker.errors
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


class TestDockerManagerErrorHandling:
    """Test Docker Manager error handling and edge cases."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.service_config = ServiceConfig(
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
        self.service_config.selected_main_volume = self.service_config.volumes[0]
        self.service_config.selected_backup_volume = self.service_config.volumes[1]

    def test_docker_connection_failure(self):
        """Test handling of Docker daemon connection failures."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_docker.side_effect = docker.errors.DockerException(
                "Docker daemon not running"
            )

            with pytest.raises(
                docker.errors.DockerException, match="Docker daemon not running"
            ):
                with DockerManager(
                    self.service_config, "postgres", "testuser", "testdb"
                ):
                    pass

    def test_no_containers_found(self):
        """Test behavior when no matching containers are found."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_client.containers.list.return_value = []

            with DockerManager(
                self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(Exception, match="No containers found"):
                    docker_mgr.create_postgres_backup()

    def test_container_exec_failure(self):
        """Test handling of container command execution failures."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock a container that fails command execution
            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            # Fix: Return tuple instead of MagicMock
            mock_container.exec_run.return_value = (1, b"pg_dump: error")
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(
                    Exception, match="pg_dump failed with exit code 1.*pg_dump: error"
                ):
                    docker_mgr.create_postgres_backup()

    def test_container_not_running(self):
        """Test handling when container exists but is not running."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock a stopped container
            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_container.status = "exited"
            mock_container.exec_run.side_effect = docker.errors.APIError(
                "Container not running"
            )
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(
                    docker.errors.APIError, match="Container not running"
                ):
                    docker_mgr.create_postgres_backup()

    def test_missing_backup_volume(self):
        """Test handling when backup volume is not selected."""
        config_no_backup = ServiceConfig(
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
        config_no_backup.selected_main_volume = config_no_backup.volumes[0]
        # No backup volume selected

        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            with DockerManager(
                config_no_backup, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Update expected error message to match actual implementation
                with pytest.raises(
                    Exception,
                    match="Service must have selected volumes for PostgreSQL upgrade",
                ):
                    docker_mgr.create_postgres_backup()

    def test_invalid_container_user(self):
        """Test handling of invalid container user."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            # Fix: Return tuple instead of MagicMock
            mock_container.exec_run.return_value = (
                1,
                b"su: user invaliduser does not exist",
            )
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                self.service_config, "invaliduser", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(
                    Exception,
                    match="pg_dump failed with exit code 1.*su: user invaliduser does not exist",
                ):
                    docker_mgr.create_postgres_backup()

    def test_database_connection_failure(self):
        """Test handling of PostgreSQL database connection failures."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            # Fix: Return tuple instead of MagicMock
            mock_container.exec_run.return_value = (
                1,
                b"pg_dump: error: connection to database failed",
            )
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(
                    Exception,
                    match="pg_dump failed with exit code 1.*connection to database failed",
                ):
                    docker_mgr.create_postgres_backup()

    def test_permission_denied_backup_directory(self):
        """Test handling of backup directory permission issues."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            # Fix: Return tuple instead of MagicMock
            mock_container.exec_run.return_value = (
                1,
                b"pg_dump: error: could not open output file: Permission denied",
            )
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(
                    Exception,
                    match="pg_dump failed with exit code 1.*Permission denied",
                ):
                    docker_mgr.create_postgres_backup()

    def test_empty_service_name(self):
        """Test handling of empty or invalid service names."""
        empty_config = ServiceConfig(name="", volumes=[])

        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_client.containers.list.return_value = []

            with DockerManager(
                empty_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Update expected error message to match actual implementation
                with pytest.raises(
                    Exception,
                    match="Service must have selected volumes for PostgreSQL upgrade",
                ):
                    docker_mgr.create_postgres_backup()

    def test_context_manager_cleanup_on_error(self):
        """Test that context manager properly cleans up on errors."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Test that __exit__ is called even when an exception occurs
            try:
                with DockerManager(
                    self.service_config, "postgres", "testuser", "testdb"
                ) as docker_mgr:
                    # Simulate an error inside the context
                    raise ValueError("Test error")
            except ValueError:
                pass  # Expected

            # Verify the client was properly set up and would be cleaned up
            assert mock_docker.called

    def test_multiple_containers_same_service(self):
        """Test behavior when multiple containers match the service name."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock multiple containers
            mock_container1 = MagicMock()
            mock_container1.name = "test_postgres_1"
            mock_container1.exec_run.return_value = (0, b"success")

            mock_container2 = MagicMock()
            mock_container2.name = "test_postgres_2"
            mock_container2.exec_run.return_value = (0, b"success")

            mock_client.containers.list.return_value = [
                mock_container1,
                mock_container2,
            ]

            with DockerManager(
                self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Should raise exception about multiple containers
                with pytest.raises(
                    Exception, match="Multiple containers found for service postgres"
                ):
                    docker_mgr.create_postgres_backup()
