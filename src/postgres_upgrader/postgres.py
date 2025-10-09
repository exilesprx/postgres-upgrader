"""
PostgreSQL upgrade workflow implementation.

This module contains the core business logic for PostgreSQL upgrades
using Docker Compose, separated from CLI concerns.
"""

from argparse import Namespace
from typing import TYPE_CHECKING

from docker.models.containers import Container

if TYPE_CHECKING:
    from .docker import DockerManager
from rich.console import Console

from . import (
    DockerManager,
    identify_service_volumes,
    parse_docker_compose,
    prompt_container_user,
    prompt_user_choice,
)

if TYPE_CHECKING:
    from .compose_inspector import DockerComposeConfig, ServiceConfig


class Postgres:
    """
    PostgreSQL upgrade orchestration class.

    This class handles the business logic for PostgreSQL database operations
    including export, import, and full upgrade workflows using Docker Compose.
    """

    def __init__(self, console: Console) -> None:
        """
        Initialize the Postgres orchestrator.

        Args:
            console: Rich Console instance for formatted output
        """
        self.console = console

    def handle_export_command(self, _args: Namespace) -> None:
        """
        Handle the export command to create a PostgreSQL backup.

        Creates a backup of the current PostgreSQL database, verifies its
        integrity, and displays statistics about the backup process.

        Args:
            args: Command line arguments (currently unused)

        Raises:
            Exception: If service is not configured for PostgreSQL export
                      or if any step in the export process fails
        """
        compose_config, selected_service, container_user, user, database = (
            self._get_selections()
        )

        if not selected_service.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL export")

        with DockerManager(
            compose_config.name, selected_service, container_user, user, database
        ) as docker_mgr:
            _, _, _ = self._create_backup_workflow(docker_mgr)

    def handle_import_command(self, _args: Namespace) -> None:
        """
        Handle the import command to restore data from a PostgreSQL backup.

        Starts the PostgreSQL service container, verifies backup volume
        mounting, imports data from backup, and updates collation version.

        Args:
            args: Command line arguments (currently unused)

        Raises:
            Exception: If service is not configured for PostgreSQL import
                      or if any step in the import process fails
        """
        compose_config, selected_service, container_user, user, database = (
            self._get_selections()
        )

        if not selected_service.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL import")

        volume = selected_service.get_backup_volume()
        if not volume:
            raise Exception("Backup volume not configured for import")

        with DockerManager(
            compose_config.name, selected_service, container_user, user, database
        ) as docker_mgr:
            container = docker_mgr.start_service_container()
            files = docker_mgr.list_files_in_volume(container, volume)
            if not files:
                raise Exception("No backup files found in backup volume")

            file = prompt_user_choice(files, "Select a backup file to import:")
            if not file:
                raise Exception("Backup file selection cancelled")

            # Verify backup integrity before import
            self.console.print("  Verifying backup integrity...")
            backup_stats = docker_mgr.verify_backup_integrity(file)
            self.console.print(
                f"   Backup verified: {backup_stats['file_size_bytes']} bytes, ~{backup_stats['estimated_table_count']} tables",
                style="green",
            )

            self._import_workflow_with_container(docker_mgr, container, file, database)

    def handle_upgrade_command(self, _args: Namespace) -> None:
        """
        Execute the complete PostgreSQL upgrade workflow.

        This method performs the full PostgreSQL upgrade sequence:
        1. Get baseline database statistics
        2. Create backup of current database
        3. Verify backup integrity
        4. Stop the PostgreSQL service container
        5. Update and build the service with new PostgreSQL version
        6. Remove the old data volume
        7. Start the service with new PostgreSQL version
        8. Verify backup volume is mounted
        9. Import data from the backup into the new database
        10. Verify import success
        11. Update collation version for the database

        Args:
            args: Command line arguments (currently unused)

        Raises:
            Exception: If service is not configured for PostgreSQL upgrade
                      or if any step in the upgrade process fails
        """
        compose_config, selected_service, container_user, user, database = (
            self._get_selections()
        )

        if not selected_service.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        # Execute the upgrade workflow
        with DockerManager(
            compose_config.name, selected_service, container_user, user, database
        ) as docker_mgr:
            original_stats, backup_path, backup_stats = self._create_backup_workflow(
                docker_mgr
            )

            docker_mgr.stop_service_container()
            docker_mgr.remove_service_container()
            docker_mgr.update_service_container()
            docker_mgr.build_service_container()
            docker_mgr.remove_service_main_volume()

            container = self._import_workflow(docker_mgr, backup_path, database)

            current_stats = docker_mgr.get_database_statistics(container)
            verification_result = self._verify_upgrade_success(
                original_stats, current_stats, backup_stats
            )
            self._display_upgrade_results(verification_result)
            if verification_result["success"] is False:
                raise Exception(
                    "PostgreSQL upgrade verification failed. Please review."
                )

            self.console.print(
                "  PostgreSQL upgrade completed successfully!", style="bold green"
            )

    def _create_backup_workflow(
        self, docker_mgr: "DockerManager"
    ) -> tuple[dict[str, int | str | bool], str, dict[str, int | str | bool]]:
        """
        Execute the backup creation workflow including statistics collection and verification.

        Args:
            docker_mgr: DockerManager instance for database operations

        Returns:
            tuple: A 3-tuple containing:
                - dict: Original database statistics
                - str: Path to the created backup file
                - dict: Backup verification statistics
        """
        self.console.print("  Collecting database statistics...")
        container = docker_mgr.find_container_by_service()
        original_stats = docker_mgr.get_database_statistics(container)
        self.console.print(
            f"   Current database: {original_stats['table_count']} tables, {original_stats['database_size']}"
        )

        backup_path = docker_mgr.create_postgres_backup()
        self.console.print(f"Backup created successfully: {backup_path}")

        self.console.print("  Verifying backup integrity...")
        backup_stats = docker_mgr.verify_backup_integrity(backup_path)
        self.console.print(
            f"   Backup verified: {backup_stats['file_size_bytes']} bytes, ~{backup_stats['estimated_table_count']} tables",
            style="green",
        )

        return original_stats, backup_path, backup_stats

    def _import_workflow(
        self, docker_mgr: "DockerManager", backup_path: str, database: str
    ) -> Container:
        """
        Execute the import workflow including container startup, volume verification, and data import.

        Args:
            docker_mgr: DockerManager instance for database operations
            backup_path: Path to the backup file to import
            database: Name of the database for import messaging
        """
        self.console.print("  Starting service container...")
        container = docker_mgr.start_service_container()

        self.console.print("  Verifying backup volume is mounted...")
        docker_mgr.verify_backup_volume_mounted(container=container)

        self.console.print(
            f"  Importing data from backup into database '{database}'..."
        )
        docker_mgr.import_data_from_backup(backup_path)
        docker_mgr.update_collation_version()
        self.console.print("  Import completed successfully!", style="bold green")
        return container

    def _import_workflow_with_container(
        self,
        docker_mgr: "DockerManager",
        container: Container,
        backup_path: str,
        database: str,
    ) -> None:
        """
        Execute the import workflow with an existing container.

        Args:
            docker_mgr: DockerManager instance for database operations
            container: Existing container to use for import
            backup_path: Path to the backup file to import
            database: Name of the database for import messaging
        """
        self.console.print("  Verifying backup volume is mounted...")
        docker_mgr.verify_backup_volume_mounted(container=container)

        self.console.print(
            f"  Importing data from backup into database '{database}'..."
        )
        docker_mgr.import_data_from_backup(backup_path)
        docker_mgr.update_collation_version()

        # Collect and display import statistics
        self.console.print("  Collecting database statistics...")
        current_stats = docker_mgr.get_database_statistics(container)
        self._display_import_stats(current_stats)

        self.console.print("  Import completed successfully!", style="bold green")

    def _get_selections(
        self,
    ) -> tuple["DockerComposeConfig", "ServiceConfig", str, str, str]:
        """
        Get user selections and credentials for the upgrade process.

        Parses Docker Compose configuration, prompts user to select
        service volumes, retrieves PostgreSQL credentials, and gets
        container user information.

        Returns:
            tuple: A 5-tuple containing:
                - DockerComposeConfig: Parsed Docker Compose configuration
                - ServiceConfig: Selected service configuration
                - str: Container user for operations
                - str: PostgreSQL username
                - str: PostgreSQL database name

        Raises:
            Exception: If Docker Compose configuration cannot be parsed,
                      no volumes are found, service selection is cancelled,
                      credentials cannot be found, or container user is invalid
        """
        try:
            compose_config = parse_docker_compose()
        except Exception as e:
            raise Exception(
                f"Error getting Docker Compose configuration: {e}. "
                "Make sure you're in a directory with a docker-compose.yml file and Docker Compose is installed."
            ) from e

        selected_service = identify_service_volumes(compose_config)
        if not selected_service:
            raise Exception("No volumes found or selection cancelled")

        service_name = selected_service.name
        if not service_name:
            raise Exception("Service name not found in selection")

        user, database = self._get_credentials(compose_config, service_name)
        if not user or not database:
            raise Exception(
                "Could not find PostgreSQL credentials in Docker Compose configuration"
            )

        container_user = prompt_container_user()
        if not container_user:
            raise Exception("A valid container user is required to proceed")

        return compose_config, selected_service, container_user, user, database

    def _get_credentials(
        self, compose_config: "DockerComposeConfig", service_name: str
    ) -> tuple[str | None, str | None]:
        """
        Get PostgreSQL credentials from resolved Docker Compose configuration.

        Extracts PostgreSQL username and database name from the Docker Compose
        environment variables or configuration for the specified service.

        Args:
            compose_config: The Docker Compose configuration object
            service_name: Name of the service to get credentials for

        Returns:
            tuple: A 2-tuple containing:
                - str | None: PostgreSQL username (None if not found)
                - str | None: PostgreSQL database name (None if not found)
        """
        user = compose_config.get_postgres_user(service_name)
        database = compose_config.get_postgres_db(service_name)
        return user, database

    def _display_import_stats(self, current_stats: dict[str, int | str | bool]) -> None:
        """
        Display import statistics to the user in a formatted manner.

        Shows basic database statistics after a successful import operation
        without requiring comparison data from original database or backup files.

        Args:
            current_stats: Database statistics dictionary from DockerManager.get_database_statistics()
                          Expected keys:
                          - table_count (int): Number of tables in the database
                          - estimated_total_rows (int): Estimated total number of rows
                          - database_size (str): Human-readable database size

        Note:
            This method is specifically designed for import operations where
            verification against original database state is not needed.
        """
        self.console.print("     Import statistics:")
        self.console.print(f"      Tables imported: {current_stats['table_count']}")
        self.console.print(
            f"      Estimated rows: {current_stats['estimated_total_rows']}"
        )
        self.console.print(f"      Database size: {current_stats['database_size']}")

    def _verify_upgrade_success(
        self,
        original_stats: dict[str, int | str | bool],
        current_stats: dict[str, int | str | bool],
        backup_stats: dict[str, int | str | bool],
    ) -> dict[str, int | str | bool | dict[str, int | str | bool] | list[str]]:
        """
        Verify that PostgreSQL upgrade was successful by comparing statistics.

        Compares current database state against both original database statistics
        and backup file statistics to ensure data was properly restored during
        the upgrade process. Performs various sanity checks including table count
        validation, backup size verification, and row count consistency checks.

        Args:
            original_stats: Statistics from the original database before upgrade
                           (from DockerManager.get_database_statistics())
            current_stats: Statistics from the current database after upgrade
                          (from DockerManager.get_database_statistics())
            backup_stats: Statistics from backup file verification
                         (from DockerManager.verify_backup_integrity())

        Returns:
            dict: Verification results containing:
                - success (bool): Whether verification passed
                - warnings (list): List of warning messages
                - current_stats (dict): Current database statistics
                - original_stats (dict): Original database statistics
                - backup_stats (dict): Backup file statistics
                - tables_restored (int): Number of tables in restored database
                - original_tables (int): Number of tables in original database
                - estimated_rows (int): Estimated total rows in restored database
                - database_size (str): Human-readable database size

        Note:
            This method does not raise exceptions for verification failures.
            Instead, it returns a result dictionary with success=False and
            detailed warning messages for the caller to handle.
        """

        verification_warnings = []
        success = True

        if current_stats["table_count"] == 0:
            verification_warnings.append("No tables found in restored database")
            success = False

        # Compare table counts (should match or be close)
        original_tables = int(original_stats.get("table_count", 0))
        current_tables = int(current_stats["table_count"])

        if abs(original_tables - current_tables) > 1:  # Allow for small differences
            verification_warnings.append(
                f"Table count mismatch. Original: {original_tables}, Current: {current_tables}"
            )
            success = False

        # Use backup_stats to verify backup was substantial enough
        backup_table_count = int(backup_stats.get("estimated_table_count", 0))
        if original_tables > 0 and backup_table_count == 0:
            verification_warnings.append(
                "Original database had tables but backup appears to contain no table definitions"
            )
            success = False

        # Verify backup file wasn't suspiciously small
        MIN_BACKUP_SIZE_BYTES = (
            1000  # Less than 1KB seems too small for a database with tables
        )
        backup_size = int(backup_stats.get("file_size_bytes", 0))
        if original_tables > 0 and backup_size < MIN_BACKUP_SIZE_BYTES:
            verification_warnings.append(
                f"Backup file is suspiciously small ({backup_size} bytes) for a database with {original_tables} tables"
            )
            success = False

        if (
            int(current_stats["estimated_total_rows"]) == 0
            and int(original_stats.get("estimated_total_rows", 0)) > 0
        ):
            verification_warnings.append(
                "No rows found in restored database, but original had data"
            )
            success = False

        return {
            "success": success,
            "warnings": verification_warnings,
            "current_stats": current_stats,
            "original_stats": original_stats,
            "backup_stats": backup_stats,
            "tables_restored": current_tables,
            "original_tables": original_tables,
            "estimated_rows": current_stats["estimated_total_rows"],
            "database_size": current_stats["database_size"],
        }

    def _display_upgrade_results(
        self,
        data: dict[str, int | str | bool | dict[str, int | str | bool] | list[str]],
    ) -> None:
        """
        Display upgrade verification results to the user in a formatted manner.

        Outputs either success information with database statistics or
        failure warnings with detailed error messages using Rich console
        formatting for better readability. This method is specifically
        designed for upgrade operations that compare original, current,
        and backup statistics.

        Args:
            data: Verification results dictionary from _verify_upgrade_success()
                 Expected keys:
                 - success (bool): Whether verification passed
                 - warnings (list): List of warning messages (if success=False)
                 - tables_restored (int): Number of tables restored
                 - original_tables (int): Number of original tables
                 - estimated_rows (int): Estimated total rows
                 - database_size (str): Human-readable database size

        Note:
            This method handles its own console output and does not return
            any values. For failed verifications, warnings are displayed
            in red styling.
        """
        if not data["success"]:
            warnings = data["warnings"]
            if isinstance(warnings, list):
                for warning in warnings:
                    self.console.print(f"     WARNING: {warning}", style="red")

            self.console.print(
                "Upgrade verification failed - data may not have been restored correctly",
                style="bold red",
            )
            return

        self.console.print("     Upgrade verification successful:")
        self.console.print(
            f"      Tables: {data['tables_restored']} (original: {data['original_tables']})"
        )
        self.console.print(f"      Estimated rows: {data['estimated_rows']}")
        self.console.print(f"      Database size: {data['database_size']}")
