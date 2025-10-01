import docker
import subprocess
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from postgres_upgrader.compose_inspector import DockerComposeConfig

if TYPE_CHECKING:
    from .prompt import ServiceVolumeConfig


class DockerManager:
    """
    Context manager for Docker client operations.
    Provides efficient client reuse across multiple operations.
    """

    def __init__(self):
        self.client: Optional[docker.DockerClient] = None

    def __enter__(self) -> "DockerManager":
        self.client = docker.from_env()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()

    def create_postgres_backup(
        self, user: str, database: str, service_config: "ServiceVolumeConfig"
    ) -> str:
        """
        Export PostgreSQL data from a Docker container to a backup file.

        Args:
            user: PostgreSQL username for authentication
            database: PostgreSQL database name to backup
            service_config: ServiceVolumeConfig object with service and volume information

        Returns:
            str: Path to the created backup file (container path)

        Raises:
            Exception: If container not found, backup fails, or multiple containers exist
        """
        if not self.client:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        service_name = service_config.name
        backup_dir = service_config.backup_volume.dir

        if not service_name:
            raise Exception("Service name not found in configuration")
        if not backup_dir:
            raise Exception("Backup directory not found in configuration")

        container = self.find_container_by_service(service_name)
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

    def stop_service_container(self, name: str):
        try:
            subprocess.run(["docker", "compose", "stop", name], check=True)
            subprocess.run(["docker", "compose", "rm", name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to stop service {name}: {e}")

    def update_service_container(self, name: str):
        try:
            subprocess.run(["docker", "compose", "pull", name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to update service {name}: {e}")

    def build_service_container(self, name: str):
        try:
            subprocess.run(["docker", "compose", "build", name], check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to build service {name}: {e}")

    def remove_service_main_volume(
        self,
        compose_config: "DockerComposeConfig",
        service_config: "ServiceVolumeConfig",
    ):
        if service_config.main_volume.name is None:
            raise Exception("Main volume not found in service configuration")

        # Find the main_volume in the compose config to ensure it exists
        target_volume = None
        for vol in compose_config.get_volumes(service_config.name):
            if vol.name == service_config.main_volume.name:
                target_volume = vol
                break

        if target_volume is None:
            raise Exception(
                f"Main volume '{service_config.main_volume.name}' not found in compose configuration"
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
                f"Failed to remove volume {service_config.main_volume.name}: {e}"
            )

    def find_container_by_service(self, name: str):
        if self.client is None:
            raise Exception(
                "DockerManager not properly initialized. Use as context manager."
            )

        containers = self.client.containers.list(
            filters={"label": f"com.docker.compose.service={name}"}
        )

        if len(containers) == 0:
            raise Exception(f"No containers found for service {name}")
        if len(containers) > 1:
            raise Exception(f"Multiple containers found for service {name}")

        return containers[0]
