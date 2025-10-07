import docker
import time
import subprocess
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from docker.models.containers import Container

if TYPE_CHECKING:
    from .compose_inspector import ServiceConfig, VolumeMount


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
        project_name: Optional[str],
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
        """
        Enter the context manager and initialize Docker client.

        Returns:
            DockerManager: Self for use in with statements
        """
        self.client = docker.from_env()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager and clean up Docker client connection.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        if self.client:
            self.client.close()

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

        backup_volume = self.service_config.get_backup_volume()
        if not backup_volume:
            raise Exception("Backup directory not found in configuration")

        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup-{date}.sql"
        backup_path = f"{backup_volume.path}/{backup_filename}"

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
        """
        Stop the configured service container using Docker Compose.

        Uses Docker Compose to gracefully stop the service container
        while preserving volumes and network configurations.

        Raises:
            Exception: If the service fails to stop or Docker Compose command fails
        """
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "stop", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to stop service {service_name}: {e}")

    def remove_service_container(self):
        """
        Remove the configured service container using Docker Compose.

        Permanently removes the service container while preserving volumes.
        This is typically called after stopping the container and before
        rebuilding with a new PostgreSQL version.

        Raises:
            Exception: If the container removal fails or Docker Compose command fails
        """
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "rm", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to remove service {service_name}: {e}")

    def update_service_container(self):
        """
        Pull the latest image for the configured service.

        Downloads the latest version of the Docker image specified in the
        Docker Compose configuration for the service. This is typically
        used to get a newer PostgreSQL version during upgrades.

        Raises:
            Exception: If image pull fails or Docker Compose command fails
        """
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "pull", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to update service {service_name}: {e}")

    def build_service_container(self):
        """
        Build the configured service container using Docker Compose.

        Rebuilds the service container from the Docker Compose configuration,
        incorporating any image updates or configuration changes. This is
        typically called after updating the service image.

        Raises:
            Exception: If the build process fails or Docker Compose command fails
        """
        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "build", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to build service {service_name}: {e}")

    def remove_service_main_volume(self):
        """
        Remove the main data volume for the configured service.

        Permanently deletes the main PostgreSQL data volume, which is necessary
        during major version upgrades to ensure the new PostgreSQL version
        creates a fresh data directory with the correct format.

        Raises:
            Exception: If service is not configured for PostgreSQL upgrade,
                      main volume doesn't have a resolved name, or volume
                      removal fails

        Warning:
            This operation is destructive and will permanently delete all
            data in the main volume. Ensure you have a backup before calling.
        """
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
        """
        Start the configured service container using Docker Compose.

        Starts the service container in detached mode and waits for it
        to become healthy before returning. This ensures the container
        is ready for database operations.

        Returns:
            Container: The Docker container object for the started service

        Raises:
            Exception: If service startup fails, container health check fails,
                      or Docker Compose command fails
        """
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

        Uses a two-tier retry strategy to handle intermittent Docker Compose
        volume mounting issues:
        1. First tier: Lightweight volume reconnection using Docker API
        2. Second tier: Full container restart as fallback

        Calculates the number of retry attempts based on timeout and sleep interval.
        At the halfway point, attempts volume reconnection before falling back
        to container restart if necessary.

        Args:
            container: Docker container object to check backup volume in
            sleep: Time to wait between retry attempts (default: 3 seconds)
            timeout: Total time to spend retrying (default: 30 seconds)

        Raises:
            Exception: If backup volume is not accessible after all retry attempts

        Note:
            The two-tier approach minimizes downtime by trying lightweight fixes
            before resorting to more disruptive container restarts.
        """
        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        backup_volume = self.service_config.get_backup_volume()
        if not backup_volume or not backup_volume.path:
            raise Exception("Backup directory not found in configuration")

        max_retries = int(timeout // sleep)

        for attempt in range(max_retries):
            try:
                container.reload()
                is_healthy = self._check_backup_volume_health(container, backup_volume)
                if is_healthy:
                    return

            except Exception:
                pass

            # If we're halfway through retries, try volume reconnection first
            if attempt == max_retries // 2:
                try:
                    # Try lightweight volume reconnection first
                    self._force_volume_reconnect(container, backup_volume)
                    time.sleep(sleep)
                    continue
                except Exception:
                    # If volume reconnection fails, fall back to container restart
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

    def _force_volume_reconnect(
        self, container: Container, backup_volume: Optional["VolumeMount"]
    ):
        """
        Force volume reconnection without full container restart.

        Attempts to re-establish Docker volume connection by performing
        filesystem sync operations and refreshing Docker's internal state
        for both the container and volume objects.

        Args:
            container: Docker container object to reconnect volumes for
            backup_volume: VolumeMount configuration for the backup volume
                          to reconnect (can be None)

        Raises:
            Exception: If volume reconnection operations fail or
                      DockerManager is not properly initialized

        Note:
            This is a lightweight alternative to full container restart
            that attempts to resolve volume mounting issues through
            Docker API operations.
        """
        if self.client is None:
            raise Exception("DockerManager not properly initialized.")

        try:
            container.exec_run(["sync"], user="root")

            if backup_volume and backup_volume.name:
                try:
                    volume = self.client.volumes.get(backup_volume.name)
                    volume.reload()
                except docker.errors.NotFound:
                    pass

            container.reload()

        except Exception as e:
            raise Exception(f"Volume reconnection failed: {e}")

    def _check_backup_volume_health(
        self, container, backup_volume: Optional["VolumeMount"]
    ) -> bool:
        """
        Check if the backup volume is properly mounted and accessible.

        Verifies both that the volume is mounted in the container and that
        it's accessible by attempting to list its contents.

        Args:
            container: Docker container object to check volume mounting in
            backup_volume: VolumeMount configuration for the backup volume
                          to check (can be None)

        Returns:
            bool: True if volume is properly mounted and accessible, False otherwise

        Note:
            This method performs both mount verification (checking container
            mount points) and accessibility verification (testing file operations).
        """
        if not backup_volume or not backup_volume.path:
            return False

        # Check if the backup volume is mounted
        mount_found = False
        for mount in container.attrs.get("Mounts", []):
            mount_path = mount.get("Destination", "")
            if mount_path == backup_volume.path:
                mount_found = True
                break

        # Check if its accessible by listing contents
        exit_code, _ = container.exec_run(
            ["ls", "-la", backup_volume.path], user=self.container_user
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
        """
        Find the Docker container for the configured service.

        Locates the running container associated with the service using
        Docker Compose labels for service name and optionally project name.

        Returns:
            Container: The Docker container object for the service

        Raises:
            Exception: If DockerManager is not properly initialized,
                      no containers are found for the service, or
                      multiple containers are found (ambiguous state)

        Note:
            Uses Docker Compose labeling convention to identify containers
            by service name and project name.
        """
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
        """
        Check if the service container is healthy after restart.

        Monitors container health status using Docker health checks, with
        a fallback to PostgreSQL-specific readiness checks if health
        checks are not configured.

        Args:
            container: Docker container object to check health for
            sleep: Time to wait between health check attempts (default: 5 seconds)
            timeout: Maximum time to wait for container to become healthy (default: 30 seconds)

        Returns:
            bool: True if container is healthy and ready, False if unhealthy
                 or not ready within the timeout period

        Note:
            Uses Docker health checks first, then falls back to pg_isready
            if health checks are not available or fail. This ensures
            compatibility with containers that may not have health checks configured.
        """
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

        Performs comprehensive validation of a PostgreSQL backup file including
        file existence, size validation, header verification, and content analysis.

        Args:
            backup_path: Container path to the backup file to verify

        Returns:
            dict: Backup statistics and validation results containing:
                - file_size_bytes (int): Size of the backup file in bytes
                - estimated_table_count (int): Estimated number of tables in backup
                - has_valid_header (bool): Whether backup has valid PostgreSQL dump header
                - backup_path (str): Path to the verified backup file

        Raises:
            Exception: If DockerManager is not properly initialized,
                      backup file is not found or inaccessible,
                      backup file is empty, cannot read backup file header,
                      or backup file is not a valid PostgreSQL dump

        Note:
            Validates both file-level properties (existence, size) and
            content-level properties (PostgreSQL dump format, table estimates).
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

        Collects comprehensive database metrics including table counts,
        row estimates, and database size information for use in backup
        verification and upgrade validation workflows.

        Returns:
            dict: Database statistics containing:
                - table_count (int): Number of user tables in the public schema
                - estimated_total_rows (int): Estimated total rows across all user tables
                - database_size (str): Human-readable database size (e.g., "15 MB")
                - database_name (str): Name of the database analyzed

        Raises:
            Exception: If DockerManager is not properly initialized,
                      container cannot be found, or database queries fail

        Note:
            Row estimates are based on PostgreSQL statistics and may not
            reflect exact counts. Database size includes indexes and other
            database objects, not just table data.
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
