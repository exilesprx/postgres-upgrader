import docker
from datetime import datetime
from typing import Dict, Any, Optional


class DockerManager:
    """
    Context manager for Docker client operations.
    Provides efficient client reuse across multiple operations.
    """
    
    def __init__(self):
        self.client: Optional[docker.DockerClient] = None
    
    def __enter__(self):
        self.client = docker.from_env()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            self.client.close()
    
    def create_postgres_backup(
        self, user: str, database: str, service_config: Dict[str, Any]
    ) -> str:
        """
        Export PostgreSQL data from a Docker container to a backup file.

        Args:
            user: PostgreSQL username for authentication
            database: PostgreSQL database name to backup
            service_config: Service volume information object containing:
                - service.name: Name of the Docker Compose service
                - service.volumes.backup.dir: Container path for backup storage (mapped to host via Docker volumes)

        Returns:
            str: Path to the created backup file (container path)

        Raises:
            Exception: If container not found, backup fails, or multiple containers exist
        """
        if not self.client:
            raise Exception("DockerManager not properly initialized. Use as context manager.")
            
        # Extract service configuration with cleaner access pattern
        service_info = service_config.get("service", {})
        service_name = service_info.get("name")
        backup_dir = service_info.get("volumes", {}).get("backup", {}).get("dir")

        if not service_name:
            raise Exception("Service name not found in configuration")
        if not backup_dir:
            raise Exception("Backup directory not found in configuration")

        containers = self.client.containers.list(
            filters={"label": f"com.docker.compose.service={service_name}"}
        )

        if len(containers) == 0:
            raise Exception(f"No containers found for service {service_name}")
        if len(containers) > 1:
            raise Exception(f"Multiple containers found for service {service_name}")

        container = containers[0]
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
