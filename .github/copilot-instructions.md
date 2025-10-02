# Copilot Instructions for postgres-upgrader

## Project Context
This is a Python project using `uv` for dependency management with a comprehensive test suite for PostgreSQL Docker upgrade tooling.

## Development Guidelines

### Always Use `uv` Commands
- ✅ Use `uv run pytest` for running tests
- ✅ Use `uv run python` for Python scripts
- ✅ Use `uv add` for adding dependencies
- ❌ Never use bare `python`, `pytest`, or `pip` commands

### Test Organization Rules
- ✅ Check existing test files before creating new ones
- ✅ Extend existing test classes when appropriate
- ✅ Current test files:
  - `test_docker.py` - DockerManager functionality
  - `test_parse_docker_compose.py` - Config parsing and volume validation
  - `test_subprocess_integration.py` - Docker Compose subprocess integration
  - `test_user_interaction.py` - User prompting and interaction

### Code Editing Best Practices
- ✅ Always check current file contents before editing (user may have made manual changes)
- ✅ Read existing code patterns before adding new functionality
- ✅ Use `replace_string_in_file` with sufficient context (3-5 lines before/after)

### Project Structure
```
src/postgres_upgrader/
├── __init__.py
├── compose_inspector.py  # Docker Compose config parsing
├── docker.py            # DockerManager class
└── prompt.py            # User interaction functions
tests/
├── test_docker.py
├── test_parse_docker_compose.py
├── test_subprocess_integration.py
└── test_user_interaction.py
```

### Key Dependencies
- Docker SDK for Python (`docker`)
- Interactive prompts (`inquirer`)
- YAML parsing (`pyyaml`)
- Testing with `pytest`

## Reinforcing Project Context

### This project:
- Uses `uv` for dependency management (has `uv.lock`)
- Has 4 test files: `test_docker.py`, `test_parse_docker_compose.py`, `test_subprocess_integration.py`, `test_user_interaction.py`
- Runs tests with `uv run pytest`
- Uses `pytest` for testing framework

### I should always:
- Use `uv run` prefix for all Python commands
- Check existing test files before creating new ones
- Extend existing test classes when appropriate
- Verify current file contents before editing (especially after user manual edits)

## Consistency Reminders
- This project uses `uv` - always prefix Python commands with `uv run`
- Avoid creating redundant test files - extend existing ones
- Check for user manual edits before making changes
- Maintain the established test organization pattern