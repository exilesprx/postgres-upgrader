import docker
import time
import subprocess
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .compose_inspector import ServiceConfig


class DockerManager:
    """
    Context manager for Docker client operations with PostgreSQL upgrade capabilities.

    Provides efficient client reuse and encapsulates service configuration
    for streamlined PostgreSQL upgrade workflows.

    Args:
        service_config: ServiceConfig with selected volumes and resolved data (required)

    Example:
        with DockerManager(selected_service) as docker_mgr:
            docker_mgr.perform_postgres_upgrade(user, database)
    """

    def __init__(self, service_config: "ServiceConfig"):
        self.client: Optional[docker.DockerClient] = None
        self.service_config = service_config

    def __enter__(self) -> "DockerManager":
        self.client = docker.from_env()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()

    def perform_postgres_upgrade(self, user: str, database: str):
        """
        Perform a complete PostgreSQL upgrade workflow.

        This method performs the full PostgreSQL upgrade sequence:
        1. Create backup of current database
        2. Stop the PostgreSQL service container
        3. Update and build the service with new PostgreSQL version
        4. Remove the old data volume
        5. Start the service with new PostgreSQL version
        6. Import data from the backup into the new database

        Args:
            user: PostgreSQL username for authentication
            database: PostgreSQL database name to backup

        Returns:
            str: Path to the created backup file (container path)

        Raises:
            Exception: If any step fails or required config is missing

        Note:
            This is a destructive operation that removes the old data volume.
            Ensure you have proper backups before running this workflow.
        """
        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        print(f"Creating backup of database '{database}' for user '{user}'...")
        backup_path = self.create_postgres_backup(user, database)
        print(f"Backup created successfully: {backup_path}")
        self.stop_service_container()
        self.update_service_container()
        self.build_service_container()
        self.remove_service_main_volume()
        self.start_service_container()
        print(f"Importing data from backup into new database '{database}'...")
        self.import_data_from_backup(user, database, backup_path)
        print("Data import completed successfully.")

    def create_postgres_backup(self, user: str, database: str) -> str:
        """
        Export PostgreSQL data from a Docker container to a backup file.

        Uses the configured service and backup volume to create a timestamped
        SQL dump of the specified PostgreSQL database.

        Args:
            user: PostgreSQL username for authentication
            database: PostgreSQL database name to backup

        Returns:
            str: Path to the created backup file (container path)

        Raises:
            Exception: If container not found, backup fails, or multiple containers exist

        Note:
            Requires ServiceConfig to be set in the DockerManager constructor.
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
        cmd = ["pg_dump", "-U", user, "-f", backup_path, database]
        exit_code, output = container.exec_run(cmd, user="postgres")

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
            subprocess.run(["docker", "compose", "rm", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to stop service {service_name}: {e}")

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

    def start_service_container(self):
        """Start the configured service container."""
        service_name = self.service_config.name
        print("Restarting service container...")
        try:
            subprocess.run(["docker", "compose", "up", "-d", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to restart service {service_name}: {e}")

    def import_data_from_backup(self, user: str, database: str, backup_path: str):
        """
        Import PostgreSQL data from a backup file into the database.

        Restores data from a SQL backup file created by create_postgres_backup()
        into the specified PostgreSQL database running in a Docker container.

        Args:
            user: PostgreSQL username for authentication
            database: PostgreSQL database name to restore data into
            backup_path: Container path to the SQL backup file to import

        Returns:
            int: Exit code (0 for success)

        Raises:
            Exception: If container not found, import fails, or DockerManager not initialized

        Note:
            The backup_path should be accessible from within the container.
            Typically this is a path in the backup volume mount.
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        if not self.service_config.is_configured_for_postgres_upgrade():
            raise Exception("Service must have selected volumes for PostgreSQL upgrade")

        status_ok = self.check_container_status()
        if status_ok is False:
            raise Exception("Container is not healthy after restart")

        container = self.find_container_by_service()
        cmd = ["psql", "-U", user, "-f", backup_path, database]
        exit_code, output = container.exec_run(cmd, user="postgres")

        if exit_code != 0:
            raise Exception(
                f"Import failed with exit code {exit_code}: {output.decode('utf-8')}"
            )

    def find_container_by_service(self):
        """Find the Docker container for the configured service."""
        if self.client is None:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        service_name = self.service_config.name
        containers = self.client.containers.list(
            filters={"label": f"com.docker.compose.service={service_name}"}
        )

        if len(containers) == 0:
            raise Exception(f"No containers found for service {service_name}")
        if len(containers) > 1:
            raise Exception(f"Multiple containers found for service {service_name}")

        return containers[0]

    def check_container_status(self, sleep=5, timeout=30) -> bool:
        """Check if the service container is healthy after restart."""
        tries = 1
        container = self.find_container_by_service()
        while True:
            container.reload()
            status = (
                container.attrs.get("State", {})
                .get("Health", {})
                .get("Status", "unhealthy")
            )
            if status == "healthy":
                break
            elif tries >= timeout / sleep and status != "healthy":
                # If health check fails, try a simple pg_isready as fallback
                exit_code, _ = container.exec_run("pg_isready", user="postgres")
                if exit_code == 0:
                    break
                return False
            else:
                tries += 1
                time.sleep(sleep)

        return True
