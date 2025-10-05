import docker
import time
from rich.console import Console
import subprocess
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from docker.models.containers import Container

if TYPE_CHECKING:
    from .compose_inspector import ServiceConfig


class DockerManager:
    """
    Context manager for Docker client operations with PostgreSQL upgrade capabilities.

    Provides efficient client reuse and encapsulates service configuration
    for streamlined PostgreSQL upgrade workflows.

    Args:
        project_name: Docker Compose project name for container filtering
        service_config: ServiceConfig with selected volumes and resolved data (required)
        container_user: User to run container commands as (e.g., "postgres")
        database_user: PostgreSQL username for authentication
        database_name: PostgreSQL database name for operations

    Example:
        with DockerManager("my_project", selected_service, "postgres", "myuser", "mydb") as docker_mgr:
            docker_mgr.perform_postgres_upgrade()
    """

    def __init__(
        self,
        project_name: str,
        service_config: "ServiceConfig",
        container_user: str,
        database_user: str,
        database_name: str,
    ):
        self.client: Optional[docker.DockerClient] = None
        self.project_name = project_name
        self.service_config = service_config
        self.container_user = container_user
        self.database_user = database_user
        self.database_name = database_name

    def __enter__(self) -> "DockerManager":
        self.client = docker.from_env()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()

    def perform_postgres_upgrade(self, console: Console):
        """
        Perform a complete PostgreSQL upgrade workflow with verification.

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
            console: Rich Console instance for formatted user output

        Raises:
            Exception: If any step fails or required config is missing

        Note:
            This is a destructive operation that removes the old data volume.
            Ensure you have proper backups before running this workflow.
        """
        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        console.print("  Collecting database statistics...")
        original_stats = self.get_database_statistics()
        console.print(
            f"   Current database: {original_stats['table_count']} tables, {original_stats['database_size']}"
        )

        console.print(
            f"  Creating backup of database '{self.database_name}' for user '{self.database_user}'..."
        )
        backup_path = self.create_postgres_backup()
        console.print(f"Backup created successfully: {backup_path}")

        # Verify backup integrity before proceeding
        console.print("  Verifying backup integrity...")
        backup_stats = self.verify_backup_integrity(backup_path)
        console.print(
            f"   Backup verified: {backup_stats['file_size_bytes']} bytes, ~{backup_stats['estimated_table_count']} tables",
            style="green",
        )

        self.stop_service_container()
        self.remove_service_container()
        self.update_service_container()
        self.build_service_container()
        self.remove_service_main_volume()
        container = self.start_service_container()

        console.print("  Verifying backup volume is mounted...")
        self.verify_backup_volume_mounted(container=container)

        console.print(
            f"  Importing data from backup into new database '{self.database_name}'..."
        )
        self.import_data_from_backup(backup_path)

        verification_result = self.verify_import_success(original_stats, backup_stats)
        self.display_verification_results(console, verification_result)
        if verification_result["success"] is False:
            console.print(
                "Import verification failed - data may not have been restored correctly",
                style="bold red",
            )
            raise Exception("PostgreSQL upgrade verification failed. Please review.")

        self.update_collation_version()
        console.print(
            "  PostgreSQL upgrade completed successfully!", style="bold green"
        )

    def create_postgres_backup(self) -> str:
        """
        Export PostgreSQL data from a Docker container to a backup file.

        Uses the configured service and backup volume to create a timestamped
        SQL dump of the configured PostgreSQL database and user.

        Returns:
            str: Path to the created backup file (container path)

        Raises:
            Exception: If container not found, backup fails, or multiple containers exist

        Note:
            Uses the database_user and database_name from the constructor.
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        backup_dir = self.service_config.get_backup_volume_path()
        if not backup_dir:
            raise Exception("Backup directory not found in configuration")

        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup-{date}.sql"
        backup_path = f"{backup_dir}/{backup_filename}"

        container = self.find_container_by_service()
        cmd = [
            "pg_dump",
            "-U",
            self.database_user,
            "-f",
            backup_path,
            self.database_name,
        ]
        exit_code, output = container.exec_run(cmd, user=self.container_user)

        if exit_code != 0:
            raise Exception(
                f"pg_dump failed with exit code {exit_code}: {output.decode('utf-8')}"
            )

        return backup_path

    def stop_service_container(self):
        """Stop and remove the configured service container."""
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "stop", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to stop service {service_name}: {e}")

    def remove_service_container(self):
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "rm", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to remove service {service_name}: {e}")

    def update_service_container(self):
        """Pull latest image for the configured service."""
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "pull", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to update service {service_name}: {e}")

    def build_service_container(self):
        """Build the configured service container."""
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "build", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to build service {service_name}: {e}")

    def remove_service_main_volume(self):
        """Remove the main volume for the configured service."""
        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        main_volume = self.service_config.selected_main_volume
        if not main_volume or not main_volume.resolved_name:
            raise Exception("Main volume does not have a resolved name")

        try:
            subprocess.run(
                ["docker", "volume", "rm", main_volume.resolved_name], check=True
            )
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to remove volume {main_volume.name}: {e}")

    def start_service_container(self) -> Container:
        """Start the configured service container."""
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "up", "-d", service_name], check=True)
            container = self.find_container_by_service()
            _ = self.check_container_status(container)

        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to restart service {service_name}: {e}")

        return container

    def verify_backup_volume_mounted(self, container, sleep=3, timeout=30):
        """
        Verify that the backup volume is properly mounted and accessible.

        Uses robust retry logic with container restart fallback to handle
        intermittent Docker Compose volume mounting issues. Calculates the number
        of retry attempts based on timeout and sleep interval.

        Args:
            container: Docker container object to check backup volume in
            sleep: Time to wait between retry attempts (default: 3 seconds)
            timeout: Total time to spend retrying (default: 30 seconds)

        Raises:
            Exception: If backup volume is not accessible after all retry attempts

        Note:
            Will attempt container restart at the halfway point of retries if
            the backup volume is still not accessible.
        """
        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        backup_dir = self.service_config.get_backup_volume_path()
        if not backup_dir:
            raise Exception("Backup directory not found in configuration")

        max_retries = int(timeout // sleep)

        for attempt in range(max_retries):
            try:
                container.reload()
                is_healthy = self._check_backup_volume_health(container, backup_dir)
                if is_healthy:
                    return

            except Exception:
                pass

            # If we're halfway through retries, try restart
            if attempt == max_retries // 2:
                try:
                    self.stop_service_container()
                    container = self.start_service_container()

                    time.sleep(sleep)
                    continue
                except subprocess.CalledProcessError:
                    # If restart fails, continue with remaining retries
                    pass

            if attempt < max_retries - 1:
                time.sleep(sleep)
            else:
                raise Exception(
                    "Backup volume failed to mount properly after container restart. This may be a Docker Compose volume mounting issue."
                )

    def _check_backup_volume_health(self, container, backup_dir) -> bool:
        # Check if the backup volume is mounted
        mount_found = False
        for mount in container.attrs.get("Mounts", []):
            mount_path = mount.get("Destination", "")
            if mount_path == backup_dir:
                mount_found = True
                break

        # Check if its accessible by listing contents
        exit_code, _ = container.exec_run(
            ["ls", "-la", backup_dir], user=self.container_user
        )
        if exit_code == 0 and mount_found:
            return True

        return False

    def import_data_from_backup(self, backup_path: str):
        """
        Import PostgreSQL data from a backup file into the database.

        Restores data from a SQL backup file created by create_postgres_backup()
        into the configured PostgreSQL database running in a Docker container.

        Args:
            backup_path: Container path to the SQL backup file to import

        Raises:
            Exception: If container not found, import fails, or DockerManager not initialized

        Note:
            The backup_path should be accessible from within the container.
            Uses the database_user and database_name from the constructor.
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        container = self.find_container_by_service()
        status_ok = self.check_container_status(container)
        if status_ok is False:
            raise Exception("Container is not healthy after restart")

        cmd = ["psql", "-U", self.database_user, "-f", backup_path, self.database_name]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        if exit_code != 0:
            raise Exception(
                f"Import failed with exit code {exit_code}: {output.decode('utf-8')}"
            )

    def update_collation_version(self):
        """
        Update collation version for the PostgreSQL database after upgrade.

        PostgreSQL major version upgrades may require updating collation versions
        to ensure compatibility with the new version's locale and collation system.
        This method refreshes the collation version for the configured database.

        Returns:
            bool: Always returns False (legacy behavior)

        Raises:
            Exception: If container not found, collation update fails, or SQL execution error

        Note:
            This should typically be called after a PostgreSQL major version upgrade
            to prevent collation-related warnings or errors.
            Uses the database_user and database_name from the constructor.
        """
        container = self.find_container_by_service()
        cmd = [
            "psql",
            "-U",
            self.database_user,
            "-d",
            self.database_name,
            "-Atc",
            f"ALTER DATABASE {self.database_name} REFRESH COLLATION VERSION;",
        ]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        if exit_code != 0:
            raise Exception(
                f"Collation update failed {exit_code}: {output.decode('utf-8')}"
            )

        return False

    def find_container_by_service(self) -> Container:
        """Find the Docker container for the configured service."""
        if self.client is None:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        service_name = self.service_config.name
        labels = [f"com.docker.compose.service={service_name}"]
        if self.project_name:
            labels.append(f"com.docker.compose.project={self.project_name}")

        containers = self.client.containers.list(filters={"label": labels})

        if len(containers) == 0:
            raise Exception(f"No containers found for service {service_name}")
        if len(containers) > 1:
            raise Exception(f"Multiple containers found for service {service_name}")

        return containers[0]

    def check_container_status(self, container, sleep=5, timeout=30) -> bool:
        """Check if the service container is healthy after restart."""
        tries = 1
        while True:
            container.reload()
            status = (
                container.attrs.get("State", {})
                .get("Health", {})
                .get("Status", "unhealthy")
            )
            if status == "healthy":
                break
            elif tries >= timeout // sleep and status != "healthy":
                # If health check fails, try a simple pg_isready as fallback
                exit_code, _ = container.exec_run(
                    "pg_isready", user=self.container_user
                )
                if exit_code == 0:
                    break
                return False
            else:
                tries += 1
                time.sleep(sleep)

        return True

    def verify_backup_integrity(self, backup_path: str) -> dict:
        """
        Verify backup file integrity and extract basic statistics.

        Args:
            backup_path: Container path to the backup file

        Returns:
            dict: Backup statistics including file size, table count estimates

        Raises:
            Exception: If backup verification fails
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        container = self.find_container_by_service()

        # Check if backup file exists and get size
        cmd = ["stat", "-c", "%s", backup_path]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        if exit_code != 0:
            raise Exception(f"Backup file {backup_path} not found or inaccessible")

        file_size = int(output.decode("utf-8").strip())
        if file_size == 0:
            raise Exception("Backup file is empty")

        # Basic SQL syntax validation - check for PostgreSQL dump header
        cmd = ["head", "-10", backup_path]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        if exit_code != 0:
            raise Exception("Cannot read backup file header")

        header = output.decode("utf-8")
        if "PostgreSQL database dump" not in header:
            raise Exception("Backup file does not appear to be a valid PostgreSQL dump")

        # Count approximate number of tables/schemas in backup
        cmd = ["grep", "-c", "CREATE TABLE", backup_path]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        table_count = int(output.decode("utf-8").strip()) if exit_code == 0 else 0

        return {
            "file_size_bytes": file_size,
            "estimated_table_count": table_count,
            "has_valid_header": True,
            "backup_path": backup_path,
        }

    def get_database_statistics(self) -> dict:
        """
        Get current database statistics for verification purposes.

        Returns:
            dict: Database statistics including table counts, row counts

        Raises:
            Exception: If statistics collection fails
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        container = self.find_container_by_service()

        # Get table count - using single line SQL to avoid whitespace issues
        sql_table_count = "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
        cmd = [
            "psql",
            "-U",
            self.database_user,
            "-d",
            self.database_name,
            "-t",
            "-c",
            sql_table_count,
        ]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        if exit_code != 0:
            raise Exception(f"Failed to get table count: {output.decode('utf-8')}")

        table_count = int(output.decode("utf-8").strip())

        # Get total row count estimate - using single line SQL
        sql_row_estimate = "SELECT COALESCE(SUM(n_tup_ins + n_tup_upd), 0) as total_rows FROM pg_stat_user_tables;"
        cmd = [
            "psql",
            "-U",
            self.database_user,
            "-d",
            self.database_name,
            "-t",
            "-c",
            sql_row_estimate,
        ]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        row_estimate = 0
        if exit_code == 0:
            result = output.decode("utf-8").strip()
            row_estimate = int(result) if result and result != "" else 0

        # Get database size
        sql_db_size = (
            f"SELECT pg_size_pretty(pg_database_size('{self.database_name}'));"
        )
        cmd = [
            "psql",
            "-U",
            self.database_user,
            "-d",
            self.database_name,
            "-t",
            "-c",
            sql_db_size,
        ]
        exit_code, output = container.exec_run(cmd, user=self.container_user)
        db_size = output.decode("utf-8").strip() if exit_code == 0 else "unknown"

        return {
            "table_count": table_count,
            "estimated_total_rows": row_estimate,
            "database_size": db_size,
            "database_name": self.database_name,
        }

    def verify_import_success(self, original_stats: dict, backup_stats: dict) -> dict:
        """
        Verify that data import was successful by comparing statistics.

        Compares current database state against both original database statistics
        and backup file statistics to ensure data was properly restored.

        Args:
            original_stats: Statistics from before backup (from get_database_statistics)
            backup_stats: Statistics from backup verification (from verify_backup_integrity)

        Returns:
            dict: Verification results with success status and details

        Raises:
            Exception: If verification checks fail
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        current_stats = self.get_database_statistics()
        verification_warnings = []
        success = True

        if current_stats["table_count"] == 0:
            verification_warnings.append("No tables found in restored database")
            success = False

        # Compare table counts (should match or be close)
        original_tables = original_stats.get("table_count", 0)
        current_tables = current_stats["table_count"]

        if abs(original_tables - current_tables) > 1:  # Allow for small differences
            verification_warnings.append(
                f"Table count mismatch. Original: {original_tables}, Current: {current_tables}"
            )
            success = False

        # Use backup_stats to verify backup was substantial enough
        backup_table_count = backup_stats.get("estimated_table_count", 0)
        if original_tables > 0 and backup_table_count == 0:
            verification_warnings.append(
                "Original database had tables but backup appears to contain no table definitions"
            )
            success = False

        # Verify backup file wasn't suspiciously small
        backup_size = backup_stats.get("file_size_bytes", 0)
        if original_tables > 0 and backup_size < 1000:  # Less than 1KB seems too small
            verification_warnings.append(
                f"Backup file is suspiciously small ({backup_size} bytes) for a database with {original_tables} tables"
            )
            success = False

        if (
            current_stats["estimated_total_rows"] == 0
            and original_stats.get("estimated_total_rows", 0) > 0
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

    def display_verification_results(self, console: Console, data: dict):
        """
        Display verification results to the user in a formatted manner.

        Args:
            console: Rich Console instance for formatted output
            data: Verification results dictionary from verify_import_success()
                 Expected keys: success, warnings, tables_restored,
                 estimated_rows, database_size
        """
        if not data["success"]:
            for warning in data["warnings"]:
                console.print(f"     WARNING: {warning}", style="red")
            return

        console.print("     Import verification successful:")
        console.print(
            f"      Tables: {data['tables_restored']} (original: {data['original_tables']})"
        )
        console.print(f"      Estimated rows: {data['estimated_rows']}")
        console.print(f"      Database size: {data['database_size']}")
