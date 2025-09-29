import docker
import yaml


def _parse_docker_compose(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def backup_location(file_path):
    compose_data = _parse_docker_compose(file_path)

    services = compose_data.get("services", {})
    postgres_service = services.get("postgres")
    volumes = postgres_service.get("volumes", {})
    for volume in volumes:
        if "backups" in volume:
            return volume.split(":")[1]
