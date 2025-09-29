import yaml
from .prompt import prompt_user_choice


def parse_docker_compose(file_path):
    """Parse a Docker Compose YAML file."""
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def extract_location(want, volumes):
    """Extract the host path for a given volume name."""
    for volume in volumes:
        if want in volume:
            return volume.split(":")[1]
    return None


def extract_name(want, volumes):
    """Extract the volume name for a given volume string."""
    for volume in volumes:
        if want in volume:
            return volume.split(":")[0]
    return None


def get_services(file_path):
    """Get list of services from a Docker Compose file."""
    compose_data = parse_docker_compose(file_path)
    return list(compose_data.get("services", {}).keys())


def get_volumes(file_path, service_name):
    """Get list of volumes for a specific service."""
    compose_data = parse_docker_compose(file_path)
    services = compose_data.get("services", {})
    service = services.get(service_name, {})
    return service.get("volumes", [])


def create_volume_info(service_name, main_volume, backup_volume, all_volumes):
    """
    Create structured volume information for a service.

    Args:
        service_name: Name of the Docker service
        main_volume: Main volume string (e.g., "database:/var/lib/postgresql/data")
        backup_volume: Backup volume string (e.g., "backups:/var/lib/postgresql/backups")
        all_volumes: List of all volumes for the service

    Returns:
        Dictionary with structured volume information
    """
    return {
        "service": {
            "name": service_name,
            "volumes": {
                "backup": {
                    "dir": extract_location(backup_volume, all_volumes),
                    "name": extract_name(backup_volume, all_volumes),
                },
                "main": {
                    "dir": extract_location(main_volume, all_volumes),
                    "name": extract_name(main_volume, all_volumes),
                },
            },
        }
    }


def identity_volumes(file_path):
    """
    Interactive version of find_location with user prompts.
    Separated for better testability.
    """
    # Get available services
    services = get_services(file_path)
    if not services:
        print("No services found in the compose file.")
        return None

    # Let user choose service
    service = prompt_user_choice(services, "Select a service to inspect:")
    if not service:
        return None

    # Get volumes for chosen service
    volumes = get_volumes(file_path, service)
    if not volumes:
        return None

    # Choose the main volume
    main = prompt_user_choice(volumes, "Select the main volume:")
    if not main:
        return None

    # Create a list of remaining volumes for backup selection
    remaining_volumes = [v for v in volumes if v != main]

    # Let user choose backup volume
    backup = prompt_user_choice(remaining_volumes, "Select the backup volume:")
    if not backup:
        return None

    # Create and return structured volume information
    return create_volume_info(service, main, backup, volumes)
