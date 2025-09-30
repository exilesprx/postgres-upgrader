# PostgreSQL Upgrader

A specialized tool for managing PostgreSQL upgrades in Docker Compose environments. This tool helps you identify and select Docker Compose services and their associated volumes for PostgreSQL upgrade operations.

## Features

- 🔍 **Interactive Service Selection**: Choose from available Docker Compose services
- 📦 **Volume Identification**: Identify main and backup volumes for PostgreSQL services
- 🎯 **Upgrade-Focused**: Specifically designed for PostgreSQL upgrade workflows
- 🖥️ **User-Friendly CLI**: Interactive prompts with arrow-key navigation
- 📝 **Graceful Fallbacks**: Text-based fallback when advanced UI isn't available
- ✅ **Well-Tested**: Comprehensive test suite with 20+ tests

## Installation

### With uv (recommended)

```bash
git clone https://github.com/exilesprx/postgres-upgrader
cd postgres-upgrader
uv sync
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

### Command Line Tool

```bash
# With uv
uv run ./main.py docker-compose.yml

# After installation with any package manager
./main.py docker-compose.yml
```

The tool will interactively prompt you to:

1. Select a Docker Compose service to inspect
2. Choose the main volume (typically your database data)
3. Select the backup volume

### Example Output

```json
{
  "service": {
    "name": "postgres",
    "volumes": {
      "backup": {
        "dir": "/var/lib/postgresql/backups",
        "name": "backups"
      },
      "main": {
        "dir": "/var/lib/postgresql/data",
        "name": "database"
      }
    }
  }
}
```

### As a Library

```python
# Direct API usage for automation
from postgres_upgrader import get_services, get_volumes, parse_docker_compose, extract_location

# Parse Docker Compose file
services = get_services("docker-compose.yml")
print("Available services:", list(services.keys()))

# Get volumes for a specific service
volumes = get_volumes(services, "postgres")
print("Postgres volumes:", volumes)

# Extract specific volume paths
backup_path = extract_location("backups", volumes)
data_path = extract_location("database", volumes)
print(f"Backup volume path: {backup_path}")
print(f"Data volume path: {data_path}")
```

```python
# For structured data creation
from postgres_upgrader import create_volume_info

# Create structured volume information (useful for automation)
volume_info = create_volume_info(
    service_name="postgres",
    main_volume="database:/var/lib/postgresql/data",
    backup_volume="backups:/var/lib/postgresql/backups",
    all_volumes=["database:/var/lib/postgresql/data", "backups:/var/lib/postgresql/backups"]
)
print(volume_info)
```

```python
# Direct API usage for automation
from postgres_upgrader import get_services, get_volumes, parse_docker_compose

# Parse Docker Compose file
compose_data = parse_docker_compose("docker-compose.yml")

# Get services
services = get_services("docker-compose.yml")
print("Available services:", list(services.keys()))

# Get volumes for a specific service
volumes = get_volumes(services, "postgres")
print("Postgres volumes:", volumes)
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
│   ├── compose_inspector.py       # Docker Compose analysis
│   └── prompt.py                  # User interaction utilities
├── tests/                         # Test suite
│   ├── test_parse_docker_compose.py  # Core functionality tests
│   └── test_user_choice.py          # User interaction tests
├── main.py                        # CLI entry point
├── pyproject.toml                 # Project configuration
└── README.md                      # This file
```

### Code Quality

```bash
# Linting and formatting (configured in pyproject.toml)
uv run ruff check
uv run ruff format

# Type checking
uv run mypy src/
```

## Requirements

- Python 3.13+
- Docker Compose files in YAML format
- Dependencies: `pyyaml`, `inquirer`, `docker`

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
