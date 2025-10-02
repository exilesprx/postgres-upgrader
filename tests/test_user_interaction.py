"""
Tests for user interaction and prompt functionality.
Comprehensive testing of user input handling, inquirer integration, and interactive workflows.
"""

import pytest
from unittest.mock import patch, MagicMock
from postgres_upgrader import (
    prompt_user_choice,
    identify_service_volumes,
    prompt_container_user,
    DockerComposeConfig,
    ServiceConfig,
    VolumeMount,
)


class TestPromptUserChoice:
    """Test the basic prompt_user_choice function with various scenarios."""

    def test_prompt_user_choice_successful_selection(self):
        """Test successful user selection from choices."""
        choices = ["Option A", "Option B", "Option C"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "Option B"}

            result = prompt_user_choice(choices, "Test prompt")

            assert result == "Option B"
            mock_inquirer.List.assert_called_once_with(
                "choice",
                message="Test prompt",
                choices=choices,
            )
            mock_inquirer.prompt.assert_called_once()

    def test_prompt_user_choice_with_default_message(self):
        """Test prompt_user_choice uses default message when none provided."""
        choices = ["Option 1", "Option 2"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "Option 1"}

            result = prompt_user_choice(choices)

            assert result == "Option 1"
            # Verify default message was used
            call_args = mock_inquirer.List.call_args
            assert call_args[1]["message"] == "Please select an option:"

    def test_prompt_user_choice_empty_choices_list(self):
        """Test prompt_user_choice handles empty choices list."""
        result = prompt_user_choice([])
        assert result is None

    def test_prompt_user_choice_user_cancellation(self):
        """Test prompt_user_choice handles user cancellation (None response)."""
        choices = ["Choice A", "Choice B"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = None  # User cancelled

            result = prompt_user_choice(choices, "Test prompt")
            assert result is None

    def test_prompt_user_choice_keyboard_interrupt(self):
        """Test prompt_user_choice handles KeyboardInterrupt gracefully."""
        choices = ["Choice A", "Choice B"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.side_effect = KeyboardInterrupt()

            with patch("builtins.print") as mock_print:
                result = prompt_user_choice(choices, "Test prompt")

                assert result is None
                mock_print.assert_called_with("\nCancelled by user")

    def test_prompt_user_choice_single_choice(self):
        """Test prompt_user_choice with only one choice available."""
        choices = ["Only Choice"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "Only Choice"}

            result = prompt_user_choice(choices, "Select one:")
            assert result == "Only Choice"

    def test_prompt_user_choice_special_characters(self):
        """Test prompt_user_choice handles choices with special characters."""
        choices = [
            "Choice with spaces",
            "Choice-with-dashes",
            "Choice_with_underscores",
            "Choice/with/slashes",
        ]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "Choice/with/slashes"}

            result = prompt_user_choice(choices, "Select special:")
            assert result == "Choice/with/slashes"

    def test_prompt_user_choice_unicode_characters(self):
        """Test prompt_user_choice handles Unicode characters."""
        choices = ["Опция А", "选项 B", "Opção C", "🚀 Rocket"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "🚀 Rocket"}

            result = prompt_user_choice(choices, "Select Unicode:")
            assert result == "🚀 Rocket"


class TestPromptContainerUser:
    """Test the prompt_container_user function for PostgreSQL container user input."""

    def test_prompt_container_user_default_value(self):
        """Test prompt_container_user uses default value 'postgres'."""
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.Text.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"container_user": "postgres"}

            result = prompt_container_user()

            assert result == "postgres"
            mock_inquirer.Text.assert_called_once_with(
                "container_user",
                message="Enter the PostgreSQL container user",
                default="postgres",
            )

    def test_prompt_container_user_custom_value(self):
        """Test prompt_container_user accepts custom container user."""
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.Text.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"container_user": "custom_user"}

            result = prompt_container_user()
            assert result == "custom_user"

    def test_prompt_container_user_empty_input(self):
        """Test prompt_container_user handles empty input."""
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.Text.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"container_user": ""}

            result = prompt_container_user()
            assert result == ""

    def test_prompt_container_user_cancellation(self):
        """Test prompt_container_user handles user cancellation."""
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.Text.return_value = "mock_question"
            mock_inquirer.prompt.return_value = None  # User cancelled

            result = prompt_container_user()
            assert result is None

    def test_prompt_container_user_keyboard_interrupt(self):
        """Test prompt_container_user handles KeyboardInterrupt."""
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.Text.return_value = "mock_question"
            mock_inquirer.prompt.side_effect = KeyboardInterrupt()

            with patch("builtins.print") as mock_print:
                result = prompt_container_user()

                assert result is None
                mock_print.assert_called_with("\nCancelled by user")

    def test_prompt_container_user_special_characters(self):
        """Test prompt_container_user accepts special characters in username."""
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.Text.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"container_user": "postgres-admin"}

            result = prompt_container_user()
            assert result == "postgres-admin"


class TestIdentifyServiceVolumes:
    """Test the identify_service_volumes interactive workflow."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        # Create mock DockerComposeConfig with test data
        self.postgres_service = ServiceConfig(
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
                VolumeMount(
                    name="logs",
                    path="/var/log/postgresql",
                    raw="logs:/var/log/postgresql",
                    resolved_name="test_logs",
                ),
            ],
        )

        self.nginx_service = ServiceConfig(
            name="nginx",
            volumes=[
                VolumeMount(
                    name="config",
                    path="/etc/nginx",
                    raw="config:/etc/nginx",
                    resolved_name="test_config",
                ),
            ],
        )

        self.compose_config = DockerComposeConfig(
            services={
                "postgres": self.postgres_service,
                "nginx": self.nginx_service,
            }
        )

    def test_identify_service_volumes_complete_workflow(self):
        """Test complete successful service and volume selection workflow."""
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            # Mock user selections in sequence
            mock_prompt.side_effect = [
                "postgres",  # Service selection
                "database:/var/lib/postgresql/data",  # Main volume selection
                "backups:/var/lib/postgresql/backups",  # Backup volume selection
            ]

            result = identify_service_volumes(self.compose_config)

            assert result is not None
            assert result.name == "postgres"
            assert result.selected_main_volume is not None
            assert result.selected_backup_volume is not None
            assert result.selected_main_volume.name == "database"
            assert result.selected_backup_volume.name == "backups"

            # Verify prompt was called 3 times with correct parameters
            assert mock_prompt.call_count == 3

            # Check service selection call
            service_call = mock_prompt.call_args_list[0]
            assert "postgres" in service_call[0][0]  # choices parameter
            assert "nginx" in service_call[0][0]
            assert "Select a service to inspect:" in service_call[0][1]

    def test_identify_service_volumes_no_services(self):
        """Test behavior when no services are available."""
        empty_config = DockerComposeConfig(services={})

        with patch("builtins.print") as mock_print:
            result = identify_service_volumes(empty_config)

            assert result is None
            mock_print.assert_called_with("No services found in the compose file.")

    def test_identify_service_volumes_user_cancels_service_selection(self):
        """Test behavior when user cancels service selection."""
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.return_value = None  # User cancelled

            result = identify_service_volumes(self.compose_config)
            assert result is None

    def test_identify_service_volumes_service_not_found(self):
        """Test behavior when selected service is not found."""
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.return_value = "nonexistent_service"

            with patch("builtins.print") as mock_print:
                result = identify_service_volumes(self.compose_config)

                assert result is None
                mock_print.assert_called_with(
                    "Service 'nonexistent_service' not found."
                )

    def test_identify_service_volumes_no_volumes_for_service(self):
        """Test behavior when selected service has no volumes."""
        service_no_volumes = ServiceConfig(name="redis", volumes=[])
        config_no_volumes = DockerComposeConfig(services={"redis": service_no_volumes})

        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.return_value = "redis"

            with patch("builtins.print") as mock_print:
                result = identify_service_volumes(config_no_volumes)

                assert result is None
                mock_print.assert_called_with("No volumes found for service 'redis'.")

    def test_identify_service_volumes_user_cancels_main_volume(self):
        """Test behavior when user cancels main volume selection."""
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.side_effect = [
                "postgres",  # Service selection
                None,  # User cancels main volume selection
            ]

            result = identify_service_volumes(self.compose_config)
            assert result is None

    def test_identify_service_volumes_user_cancels_backup_volume(self):
        """Test behavior when user cancels backup volume selection."""
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.side_effect = [
                "postgres",  # Service selection
                "database:/var/lib/postgresql/data",  # Main volume selection
                None,  # User cancels backup volume selection
            ]

            result = identify_service_volumes(self.compose_config)
            assert result is None

    def test_identify_service_volumes_single_volume_service(self):
        """Test behavior when service has only one volume."""
        single_volume_service = ServiceConfig(
            name="single",
            volumes=[
                VolumeMount(
                    name="data",
                    path="/data",
                    raw="data:/data",
                    resolved_name="test_data",
                ),
            ],
        )
        single_config = DockerComposeConfig(services={"single": single_volume_service})

        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            # Mock the responses: service selection, main volume, then empty choices handling
            def mock_prompt_response(choices, message=""):
                if "Select a service" in message:
                    return "single"
                elif "Select the main volume" in message:
                    return "data:/data"
                elif "Select the backup volume" in message:
                    # This will be called with empty choices list, should return None
                    return None
                return None

            mock_prompt.side_effect = mock_prompt_response

            result = identify_service_volumes(single_config)

            # Should return None because no backup volume choices remain
            assert result is None

            # Verify that the backup volume prompt was called with empty list
            assert mock_prompt.call_count == 3
            backup_call = mock_prompt.call_args_list[2]
            assert backup_call[0][0] == []  # Empty choices list
            assert "Select the backup volume:" in backup_call[0][1]

    def test_identify_service_volumes_volume_choice_filtering(self):
        """Test that backup volume choices exclude the selected main volume."""
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.side_effect = [
                "postgres",  # Service selection
                "database:/var/lib/postgresql/data",  # Main volume selection
                "logs:/var/log/postgresql",  # Backup volume selection
            ]

            result = identify_service_volumes(self.compose_config)

            assert result is not None
            assert result.selected_main_volume.name == "database"
            assert result.selected_backup_volume.name == "logs"

            # Check that backup volume choices excluded the main volume
            backup_call = mock_prompt.call_args_list[2]
            backup_choices = backup_call[0][0]  # choices parameter
            assert "database:/var/lib/postgresql/data" not in backup_choices
            assert "backups:/var/lib/postgresql/backups" in backup_choices
            assert "logs:/var/log/postgresql" in backup_choices


class TestUserInteractionEdgeCases:
    """Test edge cases and complex scenarios in user interaction."""

    def test_prompt_user_choice_very_long_choices_list(self):
        """Test prompt_user_choice with a very long list of choices."""
        choices = [f"Choice {i}" for i in range(100)]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "Choice 42"}

            result = prompt_user_choice(choices, "Select from many:")
            assert result == "Choice 42"

    def test_prompt_user_choice_duplicate_choices(self):
        """Test prompt_user_choice handles duplicate choices."""
        choices = ["Option A", "Option B", "Option A", "Option C"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "Option A"}

            result = prompt_user_choice(choices, "Select duplicate:")
            assert result == "Option A"

    def test_identify_service_volumes_complex_volume_names(self):
        """Test identify_service_volumes with complex volume configurations."""
        complex_service = ServiceConfig(
            name="complex-app",
            volumes=[
                VolumeMount(
                    name="app-data-primary",
                    path="/app/data/primary",
                    raw="app-data-primary:/app/data/primary",
                    resolved_name="project_app-data-primary",
                ),
                VolumeMount(
                    name="app-backup-storage",
                    path="/app/backups/storage",
                    raw="app-backup-storage:/app/backups/storage",
                    resolved_name="project_app-backup-storage",
                ),
                VolumeMount(
                    name="app-config-files",
                    path="/app/config",
                    raw="app-config-files:/app/config",
                    resolved_name="project_app-config-files",
                ),
            ],
        )

        complex_config = DockerComposeConfig(services={"complex-app": complex_service})

        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.side_effect = [
                "complex-app",
                "app-data-primary:/app/data/primary",
                "app-backup-storage:/app/backups/storage",
            ]

            result = identify_service_volumes(complex_config)

            assert result is not None
            assert result.name == "complex-app"
            assert result.selected_main_volume.name == "app-data-primary"
            assert result.selected_backup_volume.name == "app-backup-storage"

    def test_prompt_user_choice_whitespace_handling(self):
        """Test prompt_user_choice handles choices with various whitespace."""
        choices = [
            "  Choice with leading spaces",
            "Choice with trailing spaces  ",
            "  Choice with both  ",
            "\tChoice with tabs\t",
            "Choice\nwith\nnewlines",
        ]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "  Choice with both  "}

            result = prompt_user_choice(choices, "Select whitespace:")
            assert result == "  Choice with both  "

    def test_identify_service_volumes_service_environment_preservation(self):
        """Test that identify_service_volumes preserves service environment data."""
        service_with_env = ServiceConfig(
            name="postgres",
            environment={
                "POSTGRES_USER": "testuser",
                "POSTGRES_DB": "testdb",
                "POSTGRES_PASSWORD": "secret",
            },
            volumes=[
                VolumeMount(
                    name="data",
                    path="/var/lib/postgresql/data",
                    raw="data:/var/lib/postgresql/data",
                ),
                VolumeMount(
                    name="backup",
                    path="/backup",
                    raw="backup:/backup",
                ),
            ],
        )

        config_with_env = DockerComposeConfig(services={"postgres": service_with_env})

        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.side_effect = [
                "postgres",
                "data:/var/lib/postgresql/data",
                "backup:/backup",
            ]

            result = identify_service_volumes(config_with_env)

            assert result is not None
            # Verify environment is preserved
            assert result.environment["POSTGRES_USER"] == "testuser"
            assert result.environment["POSTGRES_DB"] == "testdb"
            assert result.environment["POSTGRES_PASSWORD"] == "secret"


class TestPromptIntegrationWorkflows:
    """Test integration between different prompt functions."""

    def test_full_interactive_workflow_simulation(self):
        """Test simulating a complete interactive user workflow."""
        # Create a realistic service configuration
        postgres_service = ServiceConfig(
            name="postgres",
            environment={
                "POSTGRES_USER": "myuser",
                "POSTGRES_DB": "mydb",
            },
            volumes=[
                VolumeMount(
                    name="postgres_data",
                    path="/var/lib/postgresql/data",
                    raw="postgres_data:/var/lib/postgresql/data",
                    resolved_name="project_postgres_data",
                ),
                VolumeMount(
                    name="postgres_backups",
                    path="/var/lib/postgresql/backups",
                    raw="postgres_backups:/var/lib/postgresql/backups",
                    resolved_name="project_postgres_backups",
                ),
            ],
        )

        redis_service = ServiceConfig(
            name="redis",
            volumes=[
                VolumeMount(
                    name="redis_data",
                    path="/data",
                    raw="redis_data:/data",
                    resolved_name="project_redis_data",
                ),
            ],
        )

        compose_config = DockerComposeConfig(
            services={
                "postgres": postgres_service,
                "redis": redis_service,
            }
        )

        # Mock the entire workflow
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_choice:
            mock_choice.side_effect = [
                "postgres",  # Service selection
                "postgres_data:/var/lib/postgresql/data",  # Main volume
                "postgres_backups:/var/lib/postgresql/backups",  # Backup volume
            ]

            with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
                mock_inquirer.Text.return_value = "mock_question"
                mock_inquirer.prompt.return_value = {"container_user": "postgres"}

                # Test the workflow
                selected_service = identify_service_volumes(compose_config)
                container_user = prompt_container_user()

                # Verify results
                assert selected_service is not None
                assert selected_service.name == "postgres"
                assert container_user == "postgres"

                # Verify service configuration is complete
                assert selected_service.selected_main_volume is not None
                assert selected_service.selected_backup_volume is not None
                assert selected_service.environment["POSTGRES_USER"] == "myuser"

    def test_workflow_interruption_recovery(self):
        """Test workflow behavior when user interrupts and retries."""
        postgres_service = ServiceConfig(
            name="postgres",
            volumes=[
                VolumeMount(
                    name="data",
                    path="/var/lib/postgresql/data",
                    raw="data:/var/lib/postgresql/data",
                ),
                VolumeMount(
                    name="backup",
                    path="/backup",
                    raw="backup:/backup",
                ),
            ],
        )

        compose_config = DockerComposeConfig(services={"postgres": postgres_service})

        # First attempt: user cancels during volume selection
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_choice:
            mock_choice.side_effect = [
                "postgres",  # Service selection
                None,  # User cancels main volume selection
            ]

            result1 = identify_service_volumes(compose_config)
            assert result1 is None

        # Second attempt: user completes workflow
        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_choice:
            mock_choice.side_effect = [
                "postgres",  # Service selection
                "data:/var/lib/postgresql/data",  # Main volume
                "backup:/backup",  # Backup volume
            ]

            result2 = identify_service_volumes(compose_config)
            assert result2 is not None
            assert result2.name == "postgres"


class TestPromptErrorHandling:
    """Test error handling in prompt functions."""

    def test_prompt_user_choice_inquirer_exception(self):
        """Test prompt_user_choice handles inquirer exceptions."""
        choices = ["Option A", "Option B"]

        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.side_effect = Exception("Inquirer error")

            # Should not crash, but will raise the exception
            with pytest.raises(Exception, match="Inquirer error"):
                prompt_user_choice(choices, "Test prompt")

    def test_prompt_container_user_inquirer_exception(self):
        """Test prompt_container_user handles inquirer exceptions."""
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.Text.return_value = "mock_question"
            mock_inquirer.prompt.side_effect = Exception("Inquirer text error")

            # Should not crash, but will raise the exception
            with pytest.raises(Exception, match="Inquirer text error"):
                prompt_container_user()

    def test_identify_service_volumes_service_data_corruption(self):
        """Test identify_service_volumes handles corrupted service data."""
        # Create a service with None volumes list
        corrupted_service = ServiceConfig(name="postgres")
        corrupted_service.volumes = None  # Corrupt data

        compose_config = DockerComposeConfig(services={"postgres": corrupted_service})

        with patch("postgres_upgrader.prompt.prompt_user_choice") as mock_prompt:
            mock_prompt.return_value = "postgres"

            # The function actually handles None volumes by checking if volumes exist
            # It prints "No volumes found" and returns None instead of raising TypeError
            with patch("builtins.print") as mock_print:
                result = identify_service_volumes(compose_config)

                assert result is None
                mock_print.assert_called_with(
                    "No volumes found for service 'postgres'."
                )

