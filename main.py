from docker_utils import backup_location


def main():
    location = backup_location("docker-compose.yml")


if __name__ == "__main__":
    main()
