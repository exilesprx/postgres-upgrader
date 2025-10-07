"""
Tests for postgres.py - PostgreSQL upgrade workflow orchestration.

This module tests the main Postgres class which orchestrates the entire
upgrade workflow by coordinating between components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from rich.console import Console

from postgres_upgrader.postgres import Postgres
from postgres_upgrader import ServiceConfig, VolumeMount, DockerComposeConfig


class TestPostgres:
    """Test the main Postgres workflow orchestrator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console()
        self.postgres = Postgres(self.console)

    def test_postgres_initialization(self):
        """Test that Postgres class initializes correctly."""
        assert self.postgres.console == self.console
        assert isinstance(self.postgres, Postgres)


class TestHandleExportCommand:
    """Test handle_export_command method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console()
        self.postgres = Postgres(self.console)

    @patch("postgres_upgrader.postgres.DockerManager")
    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_export_command_successful_workflow(
        self, mock_parse, mock_identify, mock_prompt, mock_docker_manager
    ):
        """Test that handle_export_command executes successfully."""
        # Setup mocks
        mock_compose_config = Mock()
        mock_compose_config.name = "test_project"
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_service.is_configured_for_postgres_upgrade.return_value = True
        mock_identify.return_value = mock_service

        mock_prompt.return_value = "postgres"

        # Mock DockerManager and its methods
        mock_docker_instance = Mock()
        mock_docker_instance.get_database_statistics.return_value = {
            "table_count": 5,
            "database_size": "25 MB",
        }
        mock_docker_instance.create_postgres_backup.return_value = "/tmp/backup.sql"
        mock_docker_instance.verify_backup_integrity.return_value = {
            "file_size_bytes": 12345,
            "estimated_table_count": 5,
        }
        mock_docker_manager.return_value.__enter__.return_value = mock_docker_instance

        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", "testdb")
        ):
            # Should not raise any exceptions
            self.postgres.handle_export_command(Mock())

        # Verify the expected calls were made
        mock_docker_instance.get_database_statistics.assert_called_once()
        mock_docker_instance.create_postgres_backup.assert_called_once()
        mock_docker_instance.verify_backup_integrity.assert_called_once_with(
            "/tmp/backup.sql"
        )


class TestHandleImportCommand:
    """Test handle_import_command method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console()
        self.postgres = Postgres(self.console)

    @patch("postgres_upgrader.postgres.DockerManager")
    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_import_command_successful_workflow(
        self, mock_parse, mock_identify, mock_prompt, mock_docker_manager
    ):
        """Test that handle_import_command executes successfully."""
        # Setup mocks
        mock_compose_config = Mock()
        mock_compose_config.name = "test_project"
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_service.is_configured_for_postgres_upgrade.return_value = True
        mock_identify.return_value = mock_service

        mock_prompt.return_value = "postgres"

        # Mock DockerManager and its methods
        mock_docker_instance = Mock()
        mock_container = Mock()
        mock_docker_instance.start_service_container.return_value = mock_container
        mock_docker_manager.return_value.__enter__.return_value = mock_docker_instance

        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", "testdb")
        ):
            # Should not raise any exceptions
            self.postgres.handle_import_command(Mock())

        # Verify the expected calls were made
        mock_docker_instance.start_service_container.assert_called_once()
        mock_docker_instance.verify_backup_volume_mounted.assert_called_once_with(
            container=mock_container
        )
        mock_docker_instance.import_data_from_backup.assert_called_once_with("")
        mock_docker_instance.update_collation_version.assert_called_once()


class TestHandleUpgradeCommand:
    """Test handle_upgrade_command workflow orchestration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console()
        self.postgres = Postgres(self.console)

    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_docker_compose_parse_failure(self, mock_parse):
        """Test handle_upgrade_command handles Docker Compose parsing failures."""
        mock_parse.side_effect = Exception("Docker Compose config error")

        with pytest.raises(Exception) as exc_info:
            self.postgres.handle_upgrade_command(Mock())

        assert "Error getting Docker Compose configuration" in str(exc_info.value)
        assert "Make sure you're in a directory with a docker-compose.yml file" in str(
            exc_info.value
        )

    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_no_service_selection(
        self, mock_parse, mock_identify, mock_prompt
    ):
        """Test handle_upgrade_command handles service selection cancellation."""
        mock_parse.return_value = Mock()
        mock_identify.return_value = None

        with pytest.raises(Exception) as exc_info:
            self.postgres.handle_upgrade_command(Mock())

        assert "No volumes found or selection cancelled" in str(exc_info.value)

    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_missing_service_name(
        self, mock_parse, mock_identify, mock_prompt
    ):
        """Test handle_upgrade_command handles missing service name."""
        mock_parse.return_value = Mock()
        mock_service = Mock()
        mock_service.name = None
        mock_identify.return_value = mock_service

        with pytest.raises(Exception) as exc_info:
            self.postgres.handle_upgrade_command(Mock())

        assert "Service name not found in selection" in str(exc_info.value)

    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_missing_credentials(
        self, mock_parse, mock_identify, mock_prompt
    ):
        """Test handle_upgrade_command handles missing PostgreSQL credentials."""
        mock_compose_config = Mock()
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_identify.return_value = mock_service

        # Mock _get_credentials to return None values
        with patch.object(self.postgres, "_get_credentials", return_value=(None, None)):
            with pytest.raises(Exception) as exc_info:
                self.postgres.handle_upgrade_command(Mock())

        assert (
            "Could not find PostgreSQL credentials in Docker Compose configuration"
            in str(exc_info.value)
        )

    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_missing_user_credential(
        self, mock_parse, mock_identify, mock_prompt
    ):
        """Test handle_upgrade_command handles missing user credential."""
        mock_compose_config = Mock()
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_identify.return_value = mock_service

        # Mock _get_credentials to return None for user
        with patch.object(
            self.postgres, "_get_credentials", return_value=(None, "testdb")
        ):
            with pytest.raises(Exception) as exc_info:
                self.postgres.handle_upgrade_command(Mock())

        assert (
            "Could not find PostgreSQL credentials in Docker Compose configuration"
            in str(exc_info.value)
        )

    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_missing_database_credential(
        self, mock_parse, mock_identify, mock_prompt
    ):
        """Test handle_upgrade_command handles missing database credential."""
        mock_compose_config = Mock()
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_identify.return_value = mock_service

        # Mock _get_credentials to return None for database
        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", None)
        ):
            with pytest.raises(Exception) as exc_info:
                self.postgres.handle_upgrade_command(Mock())

        assert (
            "Could not find PostgreSQL credentials in Docker Compose configuration"
            in str(exc_info.value)
        )

    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_missing_container_user(
        self, mock_parse, mock_identify, mock_prompt
    ):
        """Test handle_upgrade_command handles missing container user."""
        mock_compose_config = Mock()
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_identify.return_value = mock_service

        mock_prompt.return_value = None

        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", "testdb")
        ):
            with pytest.raises(Exception) as exc_info:
                self.postgres.handle_upgrade_command(Mock())

        assert "A valid container user is required to proceed" in str(exc_info.value)

    @patch("postgres_upgrader.postgres.DockerManager")
    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_successful_workflow(
        self, mock_parse, mock_identify, mock_prompt, mock_docker_manager
    ):
        """Test handle_upgrade_command executes successful complete workflow."""
        # Setup mocks for successful execution
        mock_compose_config = Mock()
        mock_compose_config.name = "test_project"
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_service.is_configured_for_postgres_upgrade.return_value = True
        mock_identify.return_value = mock_service

        mock_prompt.return_value = "postgres"

        # Mock DockerManager context manager with proper return values
        mock_docker_instance = Mock()
        mock_docker_instance.get_database_statistics.return_value = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }
        mock_docker_instance.create_postgres_backup.return_value = "/tmp/backup.sql"
        mock_docker_instance.verify_backup_integrity.return_value = {
            "file_size_bytes": 12345,
            "estimated_table_count": 5,
        }
        mock_container = Mock()
        mock_docker_instance.start_service_container.return_value = mock_container
        mock_docker_manager.return_value.__enter__.return_value = mock_docker_instance

        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", "testdb")
        ):
            # Should not raise any exceptions
            self.postgres.handle_upgrade_command(Mock())

        # Verify DockerManager was called with correct parameters
        mock_docker_manager.assert_called_once_with(
            "test_project", mock_service, "postgres", "testuser", "testdb"
        )

        # Verify the upgrade workflow was executed
        mock_docker_instance.get_database_statistics.assert_called()
        mock_docker_instance.create_postgres_backup.assert_called_once()
        mock_docker_instance.stop_service_container.assert_called_once()
        mock_docker_instance.start_service_container.assert_called_once()
        mock_docker_instance.import_data_from_backup.assert_called_once_with(
            "/tmp/backup.sql"
        )
        mock_docker_instance.update_collation_version.assert_called_once()

    @patch("postgres_upgrader.postgres.DockerManager")
    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_handle_upgrade_command_docker_manager_failure(
        self, mock_parse, mock_identify, mock_prompt, mock_docker_manager
    ):
        """Test handle_upgrade_command handles DockerManager failures."""
        # Setup mocks
        mock_compose_config = Mock()
        mock_compose_config.name = "test_project"
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_service.is_configured_for_postgres_upgrade.return_value = True
        mock_identify.return_value = mock_service

        mock_prompt.return_value = "postgres"

        # Mock DockerManager to raise an exception during backup creation
        mock_docker_instance = Mock()
        mock_docker_instance.get_database_statistics.return_value = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }
        mock_docker_instance.create_postgres_backup.side_effect = Exception(
            "Docker upgrade failed"
        )
        mock_docker_manager.return_value.__enter__.return_value = mock_docker_instance

        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", "testdb")
        ):
            with pytest.raises(Exception) as exc_info:
                self.postgres.handle_upgrade_command(Mock())

        assert "Docker upgrade failed" in str(exc_info.value)


class TestGetCredentials:
    """Test _get_credentials method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console()
        self.postgres = Postgres(self.console)

    def test_get_credentials_successful_extraction(self):
        """Test _get_credentials successfully extracts user and database."""
        mock_compose_config = Mock(spec=DockerComposeConfig)
        mock_compose_config.get_postgres_user.return_value = "testuser"
        mock_compose_config.get_postgres_db.return_value = "testdb"

        user, database = self.postgres._get_credentials(mock_compose_config, "postgres")

        assert user == "testuser"
        assert database == "testdb"
        mock_compose_config.get_postgres_user.assert_called_once_with("postgres")
        mock_compose_config.get_postgres_db.assert_called_once_with("postgres")

    def test_get_credentials_missing_user(self):
        """Test _get_credentials handles missing user."""
        mock_compose_config = Mock(spec=DockerComposeConfig)
        mock_compose_config.get_postgres_user.return_value = None
        mock_compose_config.get_postgres_db.return_value = "testdb"

        user, database = self.postgres._get_credentials(mock_compose_config, "postgres")

        assert user is None
        assert database == "testdb"

    def test_get_credentials_missing_database(self):
        """Test _get_credentials handles missing database."""
        mock_compose_config = Mock(spec=DockerComposeConfig)
        mock_compose_config.get_postgres_user.return_value = "testuser"
        mock_compose_config.get_postgres_db.return_value = None

        user, database = self.postgres._get_credentials(mock_compose_config, "postgres")

        assert user == "testuser"
        assert database is None

    def test_get_credentials_both_missing(self):
        """Test _get_credentials handles both credentials missing."""
        mock_compose_config = Mock(spec=DockerComposeConfig)
        mock_compose_config.get_postgres_user.return_value = None
        mock_compose_config.get_postgres_db.return_value = None

        user, database = self.postgres._get_credentials(mock_compose_config, "postgres")

        assert user is None
        assert database is None

    def test_get_credentials_with_different_service_name(self):
        """Test _get_credentials works with different service names."""
        mock_compose_config = Mock(spec=DockerComposeConfig)
        mock_compose_config.get_postgres_user.return_value = "customuser"
        mock_compose_config.get_postgres_db.return_value = "customdb"

        user, database = self.postgres._get_credentials(
            mock_compose_config, "custom_postgres"
        )

        assert user == "customuser"
        assert database == "customdb"
        mock_compose_config.get_postgres_user.assert_called_once_with("custom_postgres")
        mock_compose_config.get_postgres_db.assert_called_once_with("custom_postgres")


class TestPostgresIntegration:
    """Test Postgres class integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console()
        self.postgres = Postgres(self.console)

    @patch("postgres_upgrader.postgres.DockerManager")
    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_end_to_end_workflow_simulation(
        self, mock_parse, mock_identify, mock_prompt, mock_docker_manager
    ):
        """Test complete end-to-end workflow simulation with realistic data."""
        # Create realistic mock objects
        mock_compose_config = Mock()
        mock_compose_config.name = "my_postgres_project"
        mock_compose_config.get_postgres_user.return_value = "postgres_user"
        mock_compose_config.get_postgres_db.return_value = "my_database"
        mock_parse.return_value = mock_compose_config

        # Create realistic service config
        mock_service = Mock()
        mock_service.name = "database"
        mock_service.is_configured_for_postgres_upgrade.return_value = True
        mock_identify.return_value = mock_service

        mock_prompt.return_value = "postgres"

        # Mock successful DockerManager execution with proper return values
        mock_docker_instance = Mock()
        mock_docker_instance.get_database_statistics.return_value = {
            "table_count": 15,
            "database_size": "150 MB",
            "estimated_total_rows": 50000,
        }
        mock_docker_instance.create_postgres_backup.return_value = (
            "/tmp/my_postgres_project_backup.sql"
        )
        mock_docker_instance.verify_backup_integrity.return_value = {
            "file_size_bytes": 1024 * 1024 * 10,
            "estimated_table_count": 15,
        }
        mock_container = Mock()
        mock_docker_instance.start_service_container.return_value = mock_container
        mock_docker_manager.return_value.__enter__.return_value = mock_docker_instance

        # Execute the workflow
        self.postgres.handle_upgrade_command(Mock())

        # Verify complete workflow execution
        assert (
            mock_docker_instance.get_database_statistics.call_count == 2
        )  # Initial + verification
        mock_docker_instance.create_postgres_backup.assert_called_once()
        mock_docker_instance.verify_backup_integrity.assert_called_once()
        mock_docker_instance.stop_service_container.assert_called_once()
        mock_docker_instance.start_service_container.assert_called_once()
        mock_docker_instance.import_data_from_backup.assert_called_once()
        mock_docker_instance.update_collation_version.assert_called_once()

    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_error_propagation_from_parse_docker_compose(self, mock_parse):
        """Test that exceptions from parse_docker_compose are properly wrapped."""
        original_error = FileNotFoundError("docker-compose.yml not found")
        mock_parse.side_effect = original_error

        with pytest.raises(Exception) as exc_info:
            self.postgres.handle_upgrade_command(Mock())

        error_message = str(exc_info.value)
        assert "Error getting Docker Compose configuration" in error_message
        assert "docker-compose.yml not found" in error_message
        assert (
            "Make sure you're in a directory with a docker-compose.yml file"
            in error_message
        )

    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_workflow_with_empty_string_container_user(
        self, mock_parse, mock_identify, mock_prompt
    ):
        """Test handle_upgrade_command handles empty string container user."""
        mock_compose_config = Mock()
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_identify.return_value = mock_service

        mock_prompt.return_value = ""  # Empty string

        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", "testdb")
        ):
            with pytest.raises(Exception) as exc_info:
                self.postgres.handle_upgrade_command(Mock())

        assert "A valid container user is required to proceed" in str(exc_info.value)

    @patch("postgres_upgrader.postgres.DockerManager")
    @patch("postgres_upgrader.postgres.prompt_container_user")
    @patch("postgres_upgrader.postgres.identify_service_volumes")
    @patch("postgres_upgrader.postgres.parse_docker_compose")
    def test_workflow_with_whitespace_only_container_user(
        self, mock_parse, mock_identify, mock_prompt, mock_docker_manager
    ):
        """Test handle_upgrade_command handles whitespace-only container user."""
        mock_compose_config = Mock()
        mock_compose_config.name = "test_project"
        mock_parse.return_value = mock_compose_config

        mock_service = Mock()
        mock_service.name = "postgres"
        mock_service.is_configured_for_postgres_upgrade.return_value = True
        mock_identify.return_value = mock_service

        mock_prompt.return_value = "   "  # Whitespace only

        # Mock DockerManager since whitespace passes the truthiness check
        mock_docker_instance = Mock()
        mock_docker_instance.get_database_statistics.return_value = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }
        mock_docker_instance.create_postgres_backup.return_value = "/tmp/backup.sql"
        mock_docker_instance.verify_backup_integrity.return_value = {
            "file_size_bytes": 12345,
            "estimated_table_count": 5,
        }
        mock_container = Mock()
        mock_docker_instance.start_service_container.return_value = mock_container
        mock_docker_manager.return_value.__enter__.return_value = mock_docker_instance

        with patch.object(
            self.postgres, "_get_credentials", return_value=("testuser", "testdb")
        ):
            # This should actually succeed since "   " is truthy
            self.postgres.handle_upgrade_command(Mock())

        # Verify DockerManager was called with the whitespace string
        mock_docker_manager.assert_called_once_with(
            "test_project", mock_service, "   ", "testuser", "testdb"
        )


class TestPostgresHelperMethods:
    """Test Postgres helper methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Console()
        self.postgres = Postgres(self.console)

    def test_verify_import_success_successful(self):
        """Test _verify_import_success with successful import."""
        # Mock successful import verification data
        original_stats = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }

        current_stats = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }

        backup_stats = {"file_size_bytes": 12345, "estimated_table_count": 5}

        # Should not raise any exceptions for matching stats
        result = self.postgres._verify_import_success(
            original_stats, current_stats, backup_stats
        )
        assert result["success"] is True

    def test_verify_import_success_table_count_mismatch(self):
        """Test _verify_import_success with table count mismatch."""
        original_stats = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }

        current_stats = {
            "table_count": 2,  # Significantly different table count (diff > 1)
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }

        backup_stats = {"file_size_bytes": 12345, "estimated_table_count": 5}

        result = self.postgres._verify_import_success(
            original_stats, current_stats, backup_stats
        )
        assert result["success"] is False
        assert any("Table count mismatch" in warning for warning in result["warnings"])

    def test_verify_import_success_significant_row_count_difference(self):
        """Test _verify_import_success with significant row count difference."""
        original_stats = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 1000,
        }

        current_stats = {
            "table_count": 5,
            "database_size": "25 MB",
            "estimated_total_rows": 0,  # No rows found but original had data
        }

        backup_stats = {"file_size_bytes": 12345, "estimated_table_count": 5}

        result = self.postgres._verify_import_success(
            original_stats, current_stats, backup_stats
        )
        assert result["success"] is False
        assert any(
            "No rows found in restored database" in warning
            for warning in result["warnings"]
        )

    def test_display_verification_results(self):
        """Test _display_verification_results formats data correctly."""
        verification_data = {
            "success": True,
            "warnings": [],
            "tables_restored": 5,
            "original_tables": 5,
            "estimated_rows": 1000,
            "database_size": "25 MB",
        }

        # Mock console to capture output
        with patch.object(self.console, "print") as mock_print:
            self.postgres._display_verification_results(verification_data)

            # Should have printed verification results
            assert mock_print.call_count >= 3  # At least header + 2 data lines

            # Check that key information is included in output
            call_args_list = [str(call) for call in mock_print.call_args_list]
            output_text = " ".join(call_args_list)
            assert "Tables:" in output_text
            assert "Estimated rows:" in output_text
            assert "Database size:" in output_text
