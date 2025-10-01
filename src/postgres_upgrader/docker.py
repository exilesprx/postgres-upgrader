import docker
import subprocess
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from postgres_upgrader.compose_inspector import DockerComposeConfig

if TYPE_CHECKING:
    from .prompt import ServiceVolumeConfig


class DockerManager:
    """
    Context manager for Docker client operations with PostgreSQL upgrade capabilities.

    Provides efficient client reuse and encapsulates Docker Compose configuration
    for streamlined PostgreSQL upgrade workflows.

    Args:
        compose_config: DockerComposeConfig with resolved Docker Compose data
        service_config: ServiceVolumeConfig with service and volume information

    Example:
        with DockerManager(compose_config, service_config) as docker_mgr:
            docker_mgr.perform_postgres_upgrade(user, database)
    """

    def __init__(
        self,
        compose_config: Optional["DockerComposeConfig"] = None,
        service_config: Optional["ServiceVolumeConfig"] = None,
    ):
        self.client: Optional[docker.DockerClient] = None
        self.compose_config = compose_config
        self.service_config = service_config

    def __enter__(self) -> "DockerManager":
        self.client = docker.from_env()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()

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
            Requires ServiceVolumeConfig to be set in the DockerManager constructor.
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for backup creation")

        service_name = self.service_config.name
        backup_dir = self.service_config.backup_volume.dir

        if not service_name:
            raise Exception("Service name not found in configuration")
        if not backup_dir:
            raise Exception("Backup directory not found in configuration")

        container = self.find_container_by_service()
        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup-{date}.sql"
        backup_path = f"{backup_dir}/{backup_filename}"

        cmd = ["pg_dump", "-U", user, "-f", backup_path, database]

        print(f"Creating backup of database '{database}' for user '{user}'...")
        exit_code, output = container.exec_run(cmd, user="postgres")

        if exit_code != 0:
            raise Exception(
                f"pg_dump failed with exit code {exit_code}: {output.decode('utf-8')}"
            )

        print(f"Backup created successfully: {backup_path}")
        return backup_path

    def perform_postgres_upgrade(self, user: str, database: str) -> str:
        """
        Perform a complete PostgreSQL upgrade workflow.

        This method performs the full PostgreSQL upgrade sequence:
        1. Create backup of current database
        2. Stop the PostgreSQL service container
        3. Update and build the service with new PostgreSQL version
        4. Remove the old data volume
        5. Start the service with new PostgreSQL version

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
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for upgrade workflow")
        if not self.compose_config:
            raise Exception("DockerComposeConfig required for upgrade workflow")

        backup_path = self.create_postgres_backup(user, database)
        self.stop_service_container()
        self.update_service_container()
        self.build_service_container()
        self.remove_service_main_volume()
        self.start_service_container()

        return backup_path

    def stop_service_container(self):
        """Stop and remove the configured service container."""
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for stopping service")

        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "stop", service_name], check=True)
            subprocess.run(["docker", "compose", "rm", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to stop service {service_name}: {e}")

    def update_service_container(self):
        """Pull latest image for the configured service."""
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for updating service")

        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "pull", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to update service {service_name}: {e}")

    def build_service_container(self):
        """Build the configured service container."""
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for building service")

        service_name = self.service_config.name
        try:
            subprocess.run(["docker", "compose", "build", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to build service {service_name}: {e}")

    def remove_service_main_volume(self):
        """Remove the main volume for the configured service."""
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for volume removal")
        if not self.compose_config:
            raise Exception("DockerComposeConfig required for volume removal")

        if self.service_config.main_volume.name is None:
            raise Exception("Main volume not found in service configuration")

        # Find the main_volume in the compose config to ensure it exists
        target_volume = None
        for vol in self.compose_config.get_volumes(self.service_config.name):
            if vol.name == self.service_config.main_volume.name:
                target_volume = vol
                break

        if target_volume is None:
            raise Exception(
                f"Main volume '{self.service_config.main_volume.name}' not found in compose configuration"
            )

        if target_volume.resolved_name is None:
            raise Exception(
                "Main volume does not have a resolved name in compose configuration"
            )

        try:
            subprocess.run(
                ["docker", "volume", "rm", target_volume.resolved_name], check=True
            )
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Failed to remove volume {self.service_config.main_volume.name}: {e}"
            )

    def start_service_container(self):
        """Start the configured service container."""
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for starting service")

        service_name = self.service_config.name
        print("Restarting service container...")
        try:
            subprocess.run(["docker", "compose", "up", "-d", service_name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to restart service {service_name}: {e}")

    def find_container_by_service(self):
        """Find the Docker container for the configured service."""
        if self.client is None:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )
        if not self.service_config:
            raise Exception("ServiceVolumeConfig required for finding container")

        service_name = self.service_config.name
        containers = self.client.containers.list(
            filters={"label": f"com.docker.compose.service={service_name}"}
        )

        if len(containers) == 0:
            raise Exception(f"No containers found for service {service_name}")
        if len(containers) > 1:
            raise Exception(f"Multiple containers found for service {service_name}")

        return containers[0]
