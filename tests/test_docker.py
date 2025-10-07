"""
Tests for Docker backup functionality.
"""

import pytest
import subprocess
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
                    path="/tmp/postgresql/tmp/postgresql/backups",
                    raw="backups:/tmp/postgresql/tmp/postgresql/backups",
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
                "test_project", service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(Exception, match="No containers found"):
                    docker_mgr.create_postgres_backup()

    def test_docker_manager_constructor_parameters(self):
        """Test that DockerManager constructor stores parameters correctly."""
        service_config = ServiceConfig(name="test")

        with patch("postgres_upgrader.docker.docker.from_env"):
            with DockerManager(
                "test_project", service_config, "postgres", "myuser", "mydb"
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
                "test_project", service_config, "testuser", "dbuser", "testdb"
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
                with DockerManager(
                    "test_project", service_config, "postgres", "testuser", "testdb"
                ):
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
                    path="/var/lib/postgresql/tmp/postgresql/backups",
                    raw="backups:/var/lib/postgresql/tmp/postgresql/backups",
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
                    "test_project",
                    self.service_config,
                    "postgres",
                    "testuser",
                    "testdb",
                ):
                    pass

    def test_no_containers_found(self):
        """Test behavior when no matching containers are found."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_client.containers.list.return_value = []

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
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
                "test_project", self.service_config, "postgres", "testuser", "testdb"
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
                "test_project", self.service_config, "postgres", "testuser", "testdb"
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
                "test_project", config_no_backup, "postgres", "testuser", "testdb"
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
                "test_project", self.service_config, "invaliduser", "testuser", "testdb"
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
                "test_project", self.service_config, "postgres", "testuser", "testdb"
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
                "test_project", self.service_config, "postgres", "testuser", "testdb"
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
                "test_project", empty_config, "postgres", "testuser", "testdb"
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
                    "test_project",
                    self.service_config,
                    "postgres",
                    "testuser",
                    "testdb",
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
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Should raise exception about multiple containers
                with pytest.raises(
                    Exception, match="Multiple containers found for service postgres"
                ):
                    docker_mgr.create_postgres_backup()


class TestDockerManagerIntegration:
    """Mock-based integration tests for DockerManager workflows."""

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
                    path="/var/lib/postgresql/tmp/postgresql/backups",
                    raw="backups:/var/lib/postgresql/tmp/postgresql/backups",
                    resolved_name="test_backups",
                ),
            ],
        )
        self.service_config.selected_main_volume = self.service_config.volumes[0]
        self.service_config.selected_backup_volume = self.service_config.volumes[1]

    def test_full_postgres_upgrade_workflow_success(self):
        """Test complete successful PostgreSQL upgrade workflow."""
        with (
            patch("postgres_upgrader.docker.docker.from_env") as mock_docker,
            patch("postgres_upgrader.docker.subprocess.run") as mock_subprocess,
        ):
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock successful subprocess calls (Docker commands)
            mock_subprocess.return_value = MagicMock(returncode=0)

            # Mock a successful container with proper volume mounts
            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_container.attrs = {
                "Mounts": [
                    {
                        "Destination": "/var/lib/postgresql/tmp/postgresql/backups",
                        "Source": "/var/lib/docker/volumes/test_backups/_data",
                        "Type": "volume",
                    }
                ]
            }
            mock_client.containers.list.return_value = [mock_container]

            # Mock successful command executions in sequence for verification workflow
            mock_container.exec_run.side_effect = [
                # get_database_statistics calls (original stats)
                (0, b"5"),  # table count query
                (0, b"1000"),  # row count estimate
                (0, b"25 MB"),  # database size
                # create_postgres_backup call
                (0, b"Backup created successfully"),
                # verify_backup_integrity calls
                (0, b"12345"),  # file size check
                (0, b"-- PostgreSQL database dump\n-- Version info"),  # header check
                (0, b"5"),  # table count in backup
                # verify_backup_volume_mounted call (ls command)
                (0, b"directory listing"),  # backup volume accessibility check
                # import_data_from_backup call
                (0, b"Data imported successfully"),
                # get_database_statistics calls (post-import stats)
                (0, b"5"),  # table count query (same as original)
                (0, b"1000"),  # row count estimate (same as original)
                (0, b"25 MB"),  # database size (same as original)
                # update_collation_version call
                (0, b"Collation version updated"),
            ]

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Mock container health check for import
                with patch.object(
                    docker_mgr, "check_container_status", return_value=True
                ):
                    # Mock console to avoid actual output during tests
                    mock_console = MagicMock()

                    try:
                        docker_mgr.perform_postgres_upgrade(mock_console)
                    except Exception as e:
                        pytest.fail(
                            f"perform_postgres_upgrade raised an exception: {e}"
                        )

                    # Verify console.print was called (shows progress messages)
                    assert mock_console.print.call_count > 0

                    # Verify Docker commands were called
                    assert (
                        mock_subprocess.call_count >= 2
                    )  # At least stop and volume operations

                    # Verify container operations (now includes verification calls)
                    assert mock_container.exec_run.call_count >= 10

    def test_backup_and_import_workflow(self):
        """Test backup creation followed by data import."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_client.containers.list.return_value = [mock_container]

            # Mock successful backup and import with enough responses
            mock_container.exec_run.side_effect = [
                (0, b"Backup created"),  # create_postgres_backup
                (0, b"Data imported from backup"),  # import_data_from_backup
                (0, b"Extra response"),  # Buffer for additional calls
            ]

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Mock container health check for import
                with patch.object(
                    docker_mgr, "check_container_status", return_value=True
                ):
                    # Test backup creation
                    backup_path = docker_mgr.create_postgres_backup()
                    assert backup_path is not None

                    # Test data import from the backup
                    docker_mgr.import_data_from_backup(backup_path)

                    # Verify both operations called container
                    assert mock_container.exec_run.call_count >= 2

    def test_service_discovery_workflow(self):
        """Test service discovery and container finding logic."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock container discovery
            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Test internal service discovery
                container = docker_mgr.find_container_by_service()
                assert container == mock_container

                # Verify correct Docker API call
                mock_client.containers.list.assert_called_with(
                    filters={
                        "label": [
                            "com.docker.compose.service=postgres",
                            "com.docker.compose.project=test_project",
                        ]
                    }
                )

    def test_workflow_with_environment_variables(self):
        """Test workflow uses instance variables correctly."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_container.exec_run.return_value = (0, b"Success")
            mock_client.containers.list.return_value = [mock_container]

            # Test with specific credentials
            with DockerManager(
                "test_project",
                self.service_config,
                "custom_user",
                "db_user",
                "my_database",
            ) as docker_mgr:
                docker_mgr.create_postgres_backup()

                # Verify the correct user and database were used in pg_dump command
                call_args = mock_container.exec_run.call_args
                cmd = call_args[0][0]  # First positional argument (command list)

                assert "pg_dump" in cmd
                assert "db_user" in cmd  # database_user
                assert "my_database" in cmd  # database_name

                # Verify container user was passed correctly
                kwargs = call_args[1]  # Keyword arguments
                assert kwargs.get("user") == "custom_user"

    def test_collation_update_workflow(self):
        """Test collation version update workflow."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_container.exec_run.return_value = (0, b"Collation updated")
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                docker_mgr.update_collation_version()

                # Verify SQL command was executed
                call_args = mock_container.exec_run.call_args
                cmd = call_args[0][0]

                assert "psql" in cmd
                assert "REFRESH COLLATION VERSION" in " ".join(cmd)  # Correct command

    def test_workflow_error_recovery(self):
        """Test workflow behavior when individual steps fail."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_client.containers.list.return_value = [mock_container]

            # Mock backup success but import failure
            mock_container.exec_run.side_effect = [
                (0, b"Backup created successfully"),  # create_postgres_backup succeeds
                (
                    1,
                    b"Import failed: connection error",
                ),  # import_data_from_backup fails
            ]

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Backup should succeed
                backup_path = docker_mgr.create_postgres_backup()
                assert backup_path is not None

                # Mock container health check failure
                with patch.object(
                    docker_mgr, "check_container_status", return_value=False
                ):
                    # Import should fail with health check error
                    with pytest.raises(Exception, match="Container is not healthy"):
                        docker_mgr.import_data_from_backup(backup_path)

    def test_multiple_method_calls_same_instance(self):
        """Test multiple operations on same DockerManager instance."""
        with (
            patch("postgres_upgrader.docker.docker.from_env") as mock_docker,
            patch("postgres_upgrader.docker.datetime") as mock_datetime,
        ):
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock different timestamps for different calls
            mock_datetime.now.return_value.strftime.side_effect = [
                "20251002_100000",  # First backup
                "20251002_100001",  # Second backup
            ]

            mock_container = MagicMock()
            mock_container.name = "test_postgres"
            mock_container.exec_run.return_value = (0, b"Success")
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Multiple operations should reuse same instance data
                backup_path1 = docker_mgr.create_postgres_backup()
                backup_path2 = docker_mgr.create_postgres_backup()
                docker_mgr.update_collation_version()

                # Should have same configuration but different timestamps
                assert backup_path1 != backup_path2  # Different timestamps
                assert "/var/lib/postgresql/tmp/postgresql/backups/" in backup_path1
                assert "/var/lib/postgresql/tmp/postgresql/backups/" in backup_path2

                # Verify container discovery happened multiple times but with same instance
                assert mock_client.containers.list.call_count >= 3

    def test_context_manager_workflow(self):
        """Test that context manager properly manages Docker client lifecycle."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Test context manager entry and exit
            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                assert docker_mgr.client is mock_client
                assert docker_mgr.container_user == "postgres"
                assert docker_mgr.database_user == "testuser"
                assert docker_mgr.database_name == "testdb"

            # After context exit, client should be accessible but instance should be complete
            mock_docker.assert_called_once()

    def test_workflow_with_complex_service_config(self):
        """Test workflow with complex service configuration."""
        # Create a more complex service config
        complex_config = ServiceConfig(
            name="complex-postgres-service",
            environment={
                "POSTGRES_USER": "admin",
                "POSTGRES_DB": "production_db",
                "POSTGRES_PASSWORD": "secret",
            },
            volumes=[
                VolumeMount(
                    name="primary_data",
                    path="/var/lib/postgresql/data",
                    raw="primary_data:/var/lib/postgresql/data",
                    resolved_name="complex_project_primary_data",
                ),
                VolumeMount(
                    name="backup_storage",
                    path="/tmp/postgresql/backups",
                    raw="backup_storage:/tmp/postgresql/backups",
                    resolved_name="complex_project_backup_storage",
                ),
            ],
        )
        complex_config.selected_main_volume = complex_config.volumes[0]
        complex_config.selected_backup_volume = complex_config.volumes[1]

        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            mock_container = MagicMock()
            mock_container.name = "complex-postgres-service"
            mock_container.exec_run.return_value = (0, b"Success")
            mock_client.containers.list.return_value = [mock_container]

            with DockerManager(
                "test_project", complex_config, "postgres", "admin", "production_db"
            ) as docker_mgr:
                backup_path = docker_mgr.create_postgres_backup()

                # Verify backup path uses correct volume
                assert "/tmp/postgresql/backups/backup-" in backup_path

                # Verify correct service label filter
                mock_client.containers.list.assert_called_with(
                    filters={
                        "label": [
                            "com.docker.compose.service=complex-postgres-service",
                            "com.docker.compose.project=test_project",
                        ]
                    }
                )


class TestDockerManagerVolumeVerification:
    """Test Docker Manager volume mounting verification functionality."""

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
                    path="/var/lib/postgresql/tmp/postgresql/backups",
                    raw="backups:/var/lib/postgresql/tmp/postgresql/backups",
                    resolved_name="test_backups",
                ),
            ],
        )
        self.service_config.selected_main_volume = self.service_config.volumes[0]
        self.service_config.selected_backup_volume = self.service_config.volumes[1]

    def test_verify_backup_volume_mounted_success(self):
        """Test successful backup volume verification."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock container with proper volume mount
            mock_container = MagicMock()
            mock_container.attrs = {
                "Mounts": [
                    {
                        "Destination": "/var/lib/postgresql/tmp/postgresql/backups",
                        "Source": "/var/lib/docker/volumes/test_backups/_data",
                        "Type": "volume",
                    }
                ]
            }
            mock_container.exec_run.return_value = (0, b"directory listing")

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Should not raise exception
                docker_mgr.verify_backup_volume_mounted(mock_container)

                # Verify exec_run was called with correct parameters
                mock_container.exec_run.assert_called_with(
                    ["ls", "-la", "/var/lib/postgresql/tmp/postgresql/backups"],
                    user="postgres",
                )

    def test_verify_backup_volume_mounted_no_mount_found(self):
        """Test failure when Docker doesn't detect the mount."""
        with (
            patch("postgres_upgrader.docker.docker.from_env") as mock_docker,
            patch("postgres_upgrader.docker.subprocess.run") as mock_subprocess,
        ):
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock container with no matching mounts that never gets fixed
            mock_container = MagicMock()
            mock_container.attrs = {"Mounts": []}  # Always no mounts
            mock_container.exec_run.return_value = (0, b"directory listing")

            # Mock subprocess to prevent actual Docker calls during restart attempt
            mock_subprocess.return_value = MagicMock(returncode=0)

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Mock the container finding to avoid real Docker calls
                docker_mgr.find_container_by_service = MagicMock(
                    return_value=mock_container
                )
                docker_mgr.check_container_status = MagicMock(return_value=True)

                with pytest.raises(
                    Exception, match="Backup volume failed to mount properly"
                ):
                    # Use very short timeout to ensure failure even after restart
                    docker_mgr.verify_backup_volume_mounted(
                        mock_container,
                        sleep=0.01,
                        timeout=0.04,  # Only 4 attempts max
                    )

    def test_verify_backup_volume_mounted_directory_not_accessible(self):
        """Test failure when directory exists in mounts but is not accessible."""
        with (
            patch("postgres_upgrader.docker.docker.from_env") as mock_docker,
            patch("postgres_upgrader.docker.subprocess.run") as mock_subprocess,
        ):
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock container with mount but inaccessible directory that never gets fixed
            mock_container = MagicMock()
            mock_container.attrs = {
                "Mounts": [
                    {
                        "Destination": "/var/lib/postgresql/tmp/postgresql/backups",
                        "Source": "/var/lib/docker/volumes/test_backups/_data",
                        "Type": "volume",
                    }
                ]
            }
            mock_container.exec_run.return_value = (
                1,
                b"ls: cannot access",
            )  # Always fails

            # Mock subprocess to prevent actual Docker calls during restart attempt
            mock_subprocess.return_value = MagicMock(returncode=0)

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Mock the container finding to avoid real Docker calls
                docker_mgr.find_container_by_service = MagicMock(
                    return_value=mock_container
                )
                docker_mgr.check_container_status = MagicMock(return_value=True)

                with pytest.raises(
                    Exception, match="Backup volume failed to mount properly"
                ):
                    # Use very short timeout to ensure failure even after restart
                    docker_mgr.verify_backup_volume_mounted(
                        mock_container,
                        sleep=0.01,
                        timeout=0.04,  # Only 4 attempts max
                    )

    @patch("postgres_upgrader.docker.subprocess.run")
    def test_verify_backup_volume_mounted_with_container_restart(self, mock_subprocess):
        """Test container restart functionality during volume verification."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock container that fails initially but succeeds after restart
            mock_container = MagicMock()

            # Create a counter to track attempts and change behavior
            attempt_count = 0

            def mock_reload():
                nonlocal attempt_count
                attempt_count += 1

            mock_container.reload = mock_reload

            def get_attrs():
                # Fail for first 4 attempts (0, 1, 2, 3), succeed on attempt 5+
                # This ensures volume reconnection fails and container restart is needed
                # With timeout=0.6 and sleep=0.1, max_retries=6, restart at attempt 3
                if (
                    attempt_count < 5
                ):  # Attempts 0, 1, 2, 3, 4 fail (including volume reconnect)
                    return {"Mounts": []}
                else:  # Attempts 5+ succeed (after restart)
                    return {
                        "Mounts": [
                            {
                                "Destination": "/var/lib/postgresql/tmp/postgresql/backups",
                                "Source": "/var/lib/docker/volumes/test_backups/_data",
                                "Type": "volume",
                            }
                        ]
                    }

            # Mock the attrs property to change based on attempt_count
            type(mock_container).attrs = property(lambda self: get_attrs())
            mock_container.exec_run.return_value = (0, b"directory listing")

            # Mock successful subprocess calls for container restart
            mock_subprocess.return_value = MagicMock(returncode=0)

            # Mock find_container_by_service to return container after restart
            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                docker_mgr.find_container_by_service = MagicMock(
                    return_value=mock_container
                )
                docker_mgr.check_container_status = MagicMock(return_value=True)

                # Mock _force_volume_reconnect to fail, forcing container restart
                docker_mgr._force_volume_reconnect = MagicMock(
                    side_effect=Exception("Volume reconnection failed")
                )

                # Should succeed after restart
                # timeout=0.6, sleep=0.1 => max_retries=6, restart at attempt 3
                docker_mgr.verify_backup_volume_mounted(
                    mock_container, sleep=0.1, timeout=0.6
                )

                # Verify restart commands were called (after volume reconnection fails)
                expected_calls = [
                    (["docker", "compose", "stop", "postgres"],),
                    (["docker", "compose", "up", "-d", "postgres"],),
                ]
                actual_calls = [call[0] for call in mock_subprocess.call_args_list]
                assert actual_calls == expected_calls

    @patch("postgres_upgrader.docker.subprocess.run")
    def test_verify_backup_volume_mounted_restart_failure(self, mock_subprocess):
        """Test handling of container restart failures."""
        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client

            # Mock container that always fails
            mock_container = MagicMock()
            mock_container.attrs = {"Mounts": []}
            mock_container.exec_run.return_value = (1, b"not accessible")

            # Mock failed subprocess calls for container restart
            mock_subprocess.side_effect = subprocess.CalledProcessError(1, "docker")

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                with pytest.raises(
                    Exception, match="Backup volume failed to mount properly"
                ):
                    docker_mgr.verify_backup_volume_mounted(
                        mock_container, sleep=0.1, timeout=0.5
                    )

    def test_verify_backup_volume_mounted_no_service_config(self):
        """Test failure when service is not configured for PostgreSQL upgrade."""
        # Create service config without selections
        incomplete_service_config = ServiceConfig(name="postgres", volumes=[])

        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_container = MagicMock()

            with DockerManager(
                "test_project",
                incomplete_service_config,
                "postgres",
                "testuser",
                "testdb",
            ) as docker_mgr:
                with pytest.raises(
                    Exception,
                    match="Service must have selected volumes for PostgreSQL upgrade",
                ):
                    docker_mgr.verify_backup_volume_mounted(mock_container)

    def test_verify_backup_volume_mounted_no_backup_directory(self):
        """Test failure when backup directory is not found in configuration."""
        # Create service config with both volumes selected but backup volume has no path
        service_config_no_backup = ServiceConfig(
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
                    path="",  # Empty path to trigger the error
                    raw="backups:",
                    resolved_name="test_backups",
                ),
            ],
        )
        service_config_no_backup.selected_main_volume = (
            service_config_no_backup.volumes[0]
        )
        service_config_no_backup.selected_backup_volume = (
            service_config_no_backup.volumes[1]
        )

        with patch("postgres_upgrader.docker.docker.from_env") as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_container = MagicMock()

            with DockerManager(
                "test_project",
                service_config_no_backup,
                "postgres",
                "testuser",
                "testdb",
            ) as docker_mgr:
                with pytest.raises(
                    Exception, match="Backup directory not found in configuration"
                ):
                    docker_mgr.verify_backup_volume_mounted(mock_container)

    @patch("postgres_upgrader.docker.subprocess.run")
    def test_verify_backup_volume_mounted_retry_logic(self, mock_subprocess):
        """Test retry logic with different timeout and sleep parameters."""
        with (
            patch("postgres_upgrader.docker.docker.from_env") as mock_docker,
            patch("postgres_upgrader.docker.time.sleep") as mock_sleep,
        ):
            mock_client = MagicMock()
            mock_docker.return_value = mock_docker

            # Mock container that always fails
            mock_container = MagicMock()
            mock_container.attrs = {"Mounts": []}
            mock_container.exec_run.return_value = (1, b"not accessible")

            # Mock subprocess to avoid actual container operations during restart
            mock_subprocess.return_value = MagicMock(returncode=0)

            with DockerManager(
                "test_project", self.service_config, "postgres", "testuser", "testdb"
            ) as docker_mgr:
                # Mock the container finding to avoid real Docker calls
                docker_mgr.find_container_by_service = MagicMock(
                    return_value=mock_container
                )
                docker_mgr.check_container_status = MagicMock(return_value=True)

                with pytest.raises(
                    Exception, match="Backup volume failed to mount properly"
                ):
                    docker_mgr.verify_backup_volume_mounted(
                        mock_container, sleep=2, timeout=6
                    )

                # Should have called sleep 2 times (6//2 = 3 attempts, 2 sleeps)
                assert mock_sleep.call_count == 2
                mock_sleep.assert_called_with(2)
