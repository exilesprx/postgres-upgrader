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
        container_user: User to run container commands as (e.g., "postgres")
        database_user: PostgreSQL username for authentication
        database_name: PostgreSQL database name for operations

    Example:
        with DockerManager(selected_service, "postgres", "myuser", "mydb") as docker_mgr:
            docker_mgr.perform_postgres_upgrade()
    """

    def __init__(
        self,
        service_config: "ServiceConfig",
        container_user: str,
        database_user: str,
        database_name: str,
    ):
        self.client: Optional[docker.DockerClient] = None
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

    def perform_postgres_upgrade(self):
        """
        Perform a complete PostgreSQL upgrade workflow.

        This method performs the full PostgreSQL upgrade sequence:
        1. Create backup of current database
        2. Stop the PostgreSQL service container
        3. Update and build the service with new PostgreSQL version
        4. Remove the old data volume
        5. Start the service with new PostgreSQL version
        6. Import data from the backup into the new database
        7. Update collation version for the database

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

        print(
            f"Creating backup of database '{self.database_name}' for user '{self.database_user}'..."
        )
        backup_path = self.create_postgres_backup()
        print(f"Backup created successfully: {backup_path}")
        self.stop_service_container()
        self.update_service_container()
        self.build_service_container()
        self.remove_service_main_volume()
        self.start_service_container()
        print(f"Importing data from backup into new database '{self.database_name}'...")
        self.import_data_from_backup(backup_path)
        self.update_collation_version()
        print("Data import completed successfully.")

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

        status_ok = self.check_container_status()
        if status_ok is False:
            raise Exception("Container is not healthy after restart")

        container = self.find_container_by_service()
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
