"""
Tests for subprocess and Docker Compose integration.
Tests the interaction with docker compose CLI and subprocess calls.
"""

import pytest
import subprocess
import yaml
from unittest.mock import patch, MagicMock
from postgres_upgrader import parse_docker_compose, DockerComposeConfig


class TestDockerComposeSubprocessIntegration:
    """Test docker compose config subprocess integration."""

    def test_parse_docker_compose_successful_call(self):
        """Test successful docker compose config subprocess call."""
        # Mock successful docker compose config output
        mock_compose_output = """
services:
  postgres:
    environment:
      POSTGRES_USER: testuser
      POSTGRES_DB: testdb
    volumes:
    - type: volume
      source: database
      target: /var/lib/postgresql/data
    - type: volume
      source: backups
      target: /var/lib/postgresql/backups
volumes:
  database:
    name: test_project_database
  backups:
    name: test_project_backups
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock successful subprocess call
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Test the function
            config = parse_docker_compose()

            # Verify subprocess was called correctly
            mock_run.assert_called_once_with(
                ["docker", "compose", "config"],
                capture_output=True,
                text=True,
                check=True,
            )

            # Verify parsed configuration
            assert isinstance(config, DockerComposeConfig)
            assert "postgres" in config.services

            postgres_service = config.services["postgres"]
            assert postgres_service.name == "postgres"
            assert postgres_service.environment["POSTGRES_USER"] == "testuser"
            assert len(postgres_service.volumes) == 2

    def test_parse_docker_compose_command_failure(self):
        """Test handling of docker compose config command failure."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock subprocess failure
            error = subprocess.CalledProcessError(
                returncode=1,
                cmd=["docker", "compose", "config"],
                stderr="error: no configuration file provided",
            )
            mock_run.side_effect = error

            # Should raise RuntimeError with descriptive message
            with pytest.raises(
                RuntimeError, match="Failed to get docker compose config"
            ):
                parse_docker_compose()

    def test_parse_docker_compose_docker_not_found(self):
        """Test handling when docker compose is not installed."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock FileNotFoundError (command not found)
            mock_run.side_effect = FileNotFoundError("docker: command not found")

            # Should raise RuntimeError about Docker Compose not being installed
            with pytest.raises(RuntimeError, match="Docker Compose not found"):
                parse_docker_compose()

    def test_parse_docker_compose_invalid_yaml(self):
        """Test handling of invalid YAML output from docker compose config."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock subprocess returning invalid YAML
            mock_result = MagicMock()
            mock_result.stdout = "invalid: yaml: content: [unclosed"
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Should raise yaml.YAMLError
            with pytest.raises(yaml.YAMLError):
                parse_docker_compose()

    def test_parse_docker_compose_empty_output(self):
        """Test handling of empty output from docker compose config."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock subprocess returning empty output (minimal YAML)
            mock_result = MagicMock()
            mock_result.stdout = "services: {}\nvolumes: {}\n"
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Should handle empty output gracefully
            config = parse_docker_compose()
            assert isinstance(config, DockerComposeConfig)
            assert len(config.services) == 0

    def test_parse_docker_compose_completely_empty_output(self):
        """Test handling of completely empty output (None from yaml.safe_load)."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock subprocess returning truly empty output
            mock_result = MagicMock()
            mock_result.stdout = ""
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            # Should handle completely empty output gracefully
            config = parse_docker_compose()
            assert isinstance(config, DockerComposeConfig)
            assert len(config.services) == 0

    def test_parse_docker_compose_no_services(self):
        """Test handling of compose config with no services."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock compose config with no services
            mock_result = MagicMock()
            mock_result.stdout = "version: '3.8'\nvolumes: {}\n"
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            config = parse_docker_compose()
            assert isinstance(config, DockerComposeConfig)
            assert len(config.services) == 0

    def test_parse_docker_compose_complex_environment_variables(self):
        """Test parsing of complex environment variable scenarios."""
        mock_compose_output = """
services:
  postgres:
    environment:
      POSTGRES_USER: ${DB_USER:-defaultuser}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME:-production}
      CUSTOM_VAR: "value with spaces"
      NUMERIC_VAR: "12345"
    volumes:
    - type: volume
      source: data
      target: /var/lib/postgresql/data
volumes:
  data:
    name: complex_project_data_volume
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            config = parse_docker_compose()
            postgres = config.services["postgres"]

            # Verify environment variables are parsed correctly
            assert "POSTGRES_USER" in postgres.environment
            assert "CUSTOM_VAR" in postgres.environment
            assert postgres.environment["CUSTOM_VAR"] == "value with spaces"

    def test_parse_docker_compose_multiple_services(self):
        """Test parsing of compose config with multiple services."""
        mock_compose_output = """
services:
  postgres:
    environment:
      POSTGRES_USER: pguser
    volumes:
    - type: volume
      source: db_data
      target: /var/lib/postgresql/data
  redis:
    environment:
      REDIS_PASSWORD: redispass
    volumes:
    - type: volume
      source: redis_data
      target: /data
  nginx:
    volumes:
    - type: bind
      source: /host/path
      target: /etc/nginx
volumes:
  db_data:
    name: project_db_data
  redis_data:
    name: project_redis_data
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            config = parse_docker_compose()

            # Verify all services are parsed
            assert len(config.services) == 3
            assert "postgres" in config.services
            assert "redis" in config.services
            assert "nginx" in config.services

            # Verify service-specific details
            postgres = config.services["postgres"]
            assert postgres.environment["POSTGRES_USER"] == "pguser"
            assert len(postgres.volumes) == 1

            redis = config.services["redis"]
            assert redis.environment["REDIS_PASSWORD"] == "redispass"


class TestDockerComposeConfigVariations:
    """Test parsing of various Docker Compose configuration formats."""

    def test_parse_compose_v2_format(self):
        """Test parsing of Docker Compose v2 format."""
        mock_compose_output = """
version: '2.4'
services:
  postgres:
    environment:
      POSTGRES_USER: v2user
    volumes:
    - type: volume
      source: postgres_data
      target: /var/lib/postgresql/data
volumes:
  postgres_data:
    name: v2_postgres_data
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            config = parse_docker_compose()
            assert "postgres" in config.services
            assert config.services["postgres"].environment["POSTGRES_USER"] == "v2user"

    def test_parse_compose_bind_mounts(self):
        """Test parsing of bind mounts vs named volumes."""
        mock_compose_output = """
services:
  postgres:
    volumes:
    - type: volume
      source: named_volume
      target: /var/lib/postgresql/data
    - type: bind
      source: /host/backups
      target: /var/lib/postgresql/backups
volumes:
  named_volume:
    name: project_named_volume
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            config = parse_docker_compose()
            postgres = config.services["postgres"]

            # Should have both volume types
            assert len(postgres.volumes) == 2

    def test_parse_compose_external_volumes(self):
        """Test parsing of external volumes."""
        mock_compose_output = """
services:
  postgres:
    volumes:
    - type: volume
      source: external_db
      target: /var/lib/postgresql/data
volumes:
  external_db:
    external: true
    name: shared_postgres_data
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            config = parse_docker_compose()
            postgres = config.services["postgres"]
            assert len(postgres.volumes) == 1

    def test_parse_compose_with_networks(self):
        """Test parsing of compose config with custom networks."""
        mock_compose_output = """
services:
  postgres:
    environment:
      POSTGRES_USER: netuser
    volumes:
    - type: volume
      source: db_data
      target: /var/lib/postgresql/data
    networks:
    - db_network
    - monitoring
networks:
  db_network:
    name: custom_db_network
  monitoring:
    external: true
volumes:
  db_data:
    name: project_db_data
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            config = parse_docker_compose()
            assert "postgres" in config.services


class TestSubprocessErrorHandling:
    """Test subprocess error handling scenarios."""

    def test_subprocess_timeout_handling(self):
        """Test handling of subprocess timeout scenarios."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock subprocess timeout
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["docker", "compose", "config"], timeout=30
            )

            # Should raise the timeout exception
            with pytest.raises(subprocess.TimeoutExpired):
                parse_docker_compose()

    def test_subprocess_permission_denied(self):
        """Test handling of permission denied errors."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock permission denied error
            error = subprocess.CalledProcessError(
                returncode=126,
                cmd=["docker", "compose", "config"],
                stderr="docker: permission denied",
            )
            mock_run.side_effect = error

            with pytest.raises(
                RuntimeError, match="Failed to get docker compose config"
            ):
                parse_docker_compose()

    def test_subprocess_keyboard_interrupt(self):
        """Test handling of keyboard interrupt during subprocess call."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock keyboard interrupt
            mock_run.side_effect = KeyboardInterrupt()

            # Should propagate the keyboard interrupt
            with pytest.raises(KeyboardInterrupt):
                parse_docker_compose()

    def test_subprocess_output_encoding_issues(self):
        """Test handling of encoding issues in subprocess output."""
        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            # Mock subprocess with encoding issues
            mock_result = MagicMock()
            mock_result.stdout = (
                "services:\n  postgres:\n    environment:\n      UNICODE: 'café'"
            )
            mock_run.return_value = mock_result

            # Should handle Unicode correctly
            config = parse_docker_compose()
            assert "postgres" in config.services


class TestDockerComposeConfigEdgeCases:
    """Test edge cases in Docker Compose config parsing."""

    def test_parse_compose_malformed_volumes(self):
        """Test handling of malformed volume configurations."""
        mock_compose_output = """
services:
  postgres:
    volumes:
    - "invalid_volume_format"
    - type: volume
      source: valid_volume
      target: /data
volumes:
  valid_volume:
    name: project_valid_volume
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            # Should handle malformed volumes gracefully
            config = parse_docker_compose()
            postgres = config.services["postgres"]
            # Should only parse the valid volume
            assert len(postgres.volumes) == 1

    def test_parse_compose_missing_volume_definitions(self):
        """Test handling when volume is referenced but not defined."""
        mock_compose_output = """
services:
  postgres:
    volumes:
    - type: volume
      source: undefined_volume
      target: /data
volumes: {}
"""

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = mock_compose_output
            mock_run.return_value = mock_result

            # Should handle missing volume definitions
            config = parse_docker_compose()
            postgres = config.services["postgres"]
            assert len(postgres.volumes) == 1

    def test_parse_compose_very_large_config(self):
        """Test handling of very large Docker Compose configurations."""
        # Generate a large compose config
        services = {}
        for i in range(50):
            services[f"service_{i}"] = {
                "environment": {f"VAR_{j}": f"value_{j}" for j in range(20)},
                "volumes": [
                    {"type": "volume", "source": f"volume_{i}", "target": f"/data_{i}"}
                ],
            }

        large_config = {
            "services": services,
            "volumes": {
                f"volume_{i}": {"name": f"project_volume_{i}"} for i in range(50)
            },
        }

        with patch("postgres_upgrader.compose_inspector.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = yaml.dump(large_config)
            mock_run.return_value = mock_result

            # Should handle large configurations
            config = parse_docker_compose()
            assert len(config.services) == 50

