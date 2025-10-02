from typing import List, Optional, TYPE_CHECKING
import inquirer

if TYPE_CHECKING:
    from .compose_inspector import DockerComposeConfig, ServiceConfig


def prompt_user_choice(
    choices: List[str], prompt_message: str = "Please select an option:"
) -> Optional[str]:
    """
    Prompt user to select from a list of choices using inquirer with text fallback.

    Args:
        choices: List of strings to choose from
        prompt_message: Message to display to user

    Returns:
        Selected choice string, or None if cancelled
    """
    if not choices:
        return None

    try:
        # Use inquirer for better UX
        questions = [
            inquirer.List(
                "choice",
                message=prompt_message,
                choices=choices,
            ),
        ]
        answers = inquirer.prompt(questions)
        return answers["choice"] if answers else None

    except KeyboardInterrupt:
        # User cancelled with Ctrl+C - respect their intention to quit
        print("\nCancelled by user")
        return None


def identify_service_volumes(
    data: "DockerComposeConfig",
) -> Optional["ServiceConfig"]:
    """
    Interactive service and volume identification with user prompts.

    Args:
        data: Parsed Docker Compose data (from parse_docker_compose)

    Returns:
        ServiceConfig with selected volumes, or None if cancelled
    """
    # Get available services directly from data class
    if not data.services:
        print("No services found in the compose file.")
        return None

    # Let user choose service
    service_names = list(data.services.keys())
    service_name = prompt_user_choice(service_names, "Select a service to inspect:")
    if not service_name:
        return None

    # Get volumes for chosen service using the data class method
    service = data.get_service(service_name)
    if not service:
        print(f"Service '{service_name}' not found.")
        return None

    volumes = service.volumes
    if not volumes:
        print(f"No volumes found for service '{service_name}'.")
        return None

    # Convert VolumeMount objects to strings for user selection
    volume_choices = [vol.raw for vol in volumes]

    # Choose the main volume
    main_choice = prompt_user_choice(volume_choices, "Select the main volume:")
    if not main_choice:
        return None

    # Find the corresponding VolumeMount object
    main_volume = next(vol for vol in volumes if vol.raw == main_choice)

    # Create a list of remaining volumes for backup selection
    remaining_choices = [vol.raw for vol in volumes if vol.raw != main_choice]

    # Let user choose backup volume
    backup_choice = prompt_user_choice(remaining_choices, "Select the backup volume:")
    if not backup_choice:
        return None

    # Find the corresponding VolumeMount object
    backup_volume = next(vol for vol in volumes if vol.raw == backup_choice)

    # Set the selected volumes on the service and return it
    service.select_volumes(main_volume, backup_volume)
    return service


def prompt_container_user() -> Optional[str]:
    """
    Prompt user to input a container user (e.g., 'postgres').

    Args:
        message: Prompt message to display

    Returns:
        User input string, or None if cancelled
    """
    try:
        questions = [
            inquirer.Text(
                "container_user",
                message="Enter the PostgreSQL container user (e.g., 'postgres'):",
                default="postgres",
            ),
        ]
        answers = inquirer.prompt(questions)
        return answers["container_user"] if answers else None

    except KeyboardInterrupt:
        print("\nCancelled by user")
        return None
