import docker
import yaml


def parse_docker_compose(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def backup_location(compose_data):
    services = compose_data.get("services", {})
    postgres_service = services.get("postgres")
    volumes = postgres_service.get("volumes", {})
    for volume in volumes:
        if "backups" in volume:
            return volume.split(":")[1]

    raise ValueError("No backup volume found in docker-compose.yml")


def main():
    compose_data = parse_docker_compose("docker-compose.yml")
    location = backup_location(compose_data)


if __name__ == "__main__":
    main()
