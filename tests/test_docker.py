"""
Tests for Docker backup functionality.
"""
import pytest
from unittest.mock import MagicMock, patch
from postgres_upgrader import export_postgres_data


class TestExportPostgresData:
    """Test PostgreSQL backup export functionality."""

    def test_export_postgres_data_parameters(self):
        """Test that export_postgres_data function accepts correct parameters."""
        # This test just verifies the function signature without Docker dependencies
        
        # Mock service config
        service_config = MagicMock()
        service_config.service.name = "postgres"
        service_config.service.volumes.backup.dir = "/var/lib/postgresql/backups"
        
        # The function should be callable with these parameters
        # We can't actually run it without Docker, but we can verify it exists
        assert callable(export_postgres_data)
        
        # Mock Docker to test the function structure
        with patch('postgres_upgrader.docker.docker.from_env') as mock_docker:
            mock_client = MagicMock()
            mock_docker.return_value = mock_client
            mock_client.containers.list.return_value = []  # No containers found
            
            # Should raise exception when no containers found
            with pytest.raises(Exception, match="No containers found"):
                export_postgres_data("testuser", "testdb", service_config)