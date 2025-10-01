# PostgreSQL Upgrader

A specialized tool for managing PostgreSQL upgrades in Docker Compose environments. This tool helps you identify and select Docker Compose services and their associated volumes for PostgreSQL upgrade operations.

## Features

- 🔍 **Interactive Service Selection**: Choose from available Docker Compose services
- 📦 **Volume Identification**: Identify main and backup volumes for PostgreSQL services
- 🎯 **Upgrade-Focused**: Specifically designed for PostgreSQL upgrade workflows
- 🖥️ **User-Friendly CLI**: Interactive prompts with arrow-key navigation
- 📝 **Intuitive Interface**: Interactive prompts with arrow-key navigation
- ✅ **Well-Tested**: Comprehensive test suite with 15+ tests

## Installation

### With uv (recommended)

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
uv sync

# For development (includes ruff for code formatting/linting)
uv sync --group dev
```

### With pip

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
pip install -e .
```

### With poetry

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
poetry install
```

## Usage

### Prerequisites

The tool needs PostgreSQL credentials which can be provided in two ways:

1. **Via `.env` file** (recommended):

   ```bash
   POSTGRES_USER=your_postgres_user
   POSTGRES_DB=your_database_name
   ```

2. **Via Docker Compose environment variables**: The tool will automatically fall back to reading credentials from your `docker-compose.yml` file if no `.env` file is found.

### Command Line Tool

```bash
# With uv
uv run ./main.py docker-compose.yml

# After installation with any package manager
./main.py docker-compose.yml
```

The tool will:

1. Parse your Docker Compose file
2. Interactively prompt you to select a service
3. Let you choose main and backup volumes
4. Attempt to create a PostgreSQL backup using the selected configuration

### Example Output

```
[?] Select a service to inspect::
 > postgres
   nginx

[?] Select the main volume::
 > database:/var/lib/postgresql/data
   backups:/var/lib/postgresql/backups

[?] Select the backup volume::
 > backups:/var/lib/postgresql/backups

Backup location: /var/lib/postgresql/backups
```

### As a Library

```python
# Basic usage - parse and analyze Docker Compose files
from postgres_upgrader import parse_docker_compose

# Parse Docker Compose file once
compose_data = parse_docker_compose("docker-compose.yml")

# Get services from parsed data
services = compose_data.services
print("Available services:", list(services.keys()))

# Get volumes for a specific service
volumes = compose_data.get_volumes("postgres")
print("Postgres volumes:", [v.raw for v in volumes])

# Access specific volume information directly from VolumeMount objects
backup_volume = next((v for v in volumes if v.name == "backups"), None)
data_volume = next((v for v in volumes if v.name == "database"), None)

if backup_volume:
    print(f"Backup volume path: {backup_volume.path}")
if data_volume:
    print(f"Data volume path: {data_volume.path}")
```

```python
# Interactive volume selection
from postgres_upgrader import parse_docker_compose, identify_service_volumes

# Parse compose file and interactively select volumes
compose_data = parse_docker_compose("docker-compose.yml")
volume_config = identify_service_volumes(compose_data)

if volume_config:
    service_name = volume_config.name
    backup_dir = volume_config.backup_volume.dir
    print(f"Selected service: {service_name}")
    print(f"Backup directory: {backup_dir}")
```

```python
# Full backup workflow with credential fallback
from postgres_upgrader import (
    parse_docker_compose,
    identify_service_volumes,
    DockerManager,
    get_database_user,
    get_database_name
)

# Parse and select volumes
compose_data = parse_docker_compose("docker-compose.yml")
volume_config = identify_service_volumes(compose_data)

if volume_config:
    service_name = volume_config.name

    # Try to get credentials from .env file, fallback to Docker Compose
    try:
        user = get_database_user()
        database = get_database_name()
    except Exception:
        # Fallback to Docker Compose environment variables using data class methods
        user = compose_data.get_postgres_user(service_name)
        database = compose_data.get_postgres_db(service_name)

    # Create backup using DockerManager
    with DockerManager() as docker_mgr:
        backup_path = docker_mgr.create_postgres_backup(user, database, volume_config)
        print(f"Backup created: {backup_path}")
```

## Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_parse_docker_compose.py

# Run with coverage
uv run pytest --cov=src/postgres_upgrader
```

### Project Structure

```
postgres-upgrader/
├── src/postgres_upgrader/          # Main package
│   ├── __init__.py                 # Package exports
│   ├── compose_inspector.py       # Docker Compose parsing and analysis
│   ├── prompt.py                  # User interaction and volume selection
│   ├── docker.py                  # Docker operations and PostgreSQL backup
│   └── env.py                     # Environment configuration management
├── tests/                         # Test suite
│   ├── test_docker.py              # Docker operations tests
│   ├── test_parse_docker_compose.py  # Core functionality tests
│   └── test_user_choice.py          # User interaction tests
├── main.py                        # CLI entry point
├── pyproject.toml                 # Project configuration
├── uv.lock                        # Dependency lock file (uv)
└── README.md                      # This file
```

### Code Quality

```bash
# Running tests (included in project dependencies)
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_parse_docker_compose.py
```

#### Development Tools

The project includes development dependencies for code quality:

```bash
# Install with dev dependencies (includes ruff)
uv sync --group dev

# Code linting and formatting (ruff is included as dev dependency)
uv run ruff check          # Linting
uv run ruff format         # Code formatting

# Optional: Install additional tools
uv add --dev mypy coverage

# With additional tools:
uv run mypy src/           # Type checking
uv run pytest --cov=src/postgres_upgrader  # Coverage reporting
```

## Requirements

- Python 3.13+
- Docker Compose files in YAML format with PostgreSQL service
- PostgreSQL credentials either in `.env` file or Docker Compose environment variables
- Dependencies: `pyyaml`, `inquirer`, `docker`, `python-dotenv`, `pytest`

## Future Enhancements

This tool is designed as the foundation for a complete PostgreSQL upgrade solution that will include:

- 🔄 Automated backup creation before upgrades
- 🐳 Docker image building for new PostgreSQL versions
- ⚡ Service orchestration (stop/start PostgreSQL containers)
- 📥 Backup import and restoration
- 🔧 Complete upgrade workflow automation

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`uv run pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

[Add your license here]
