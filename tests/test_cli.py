"""
Tests for CLI infrastructure components.
"""

import argparse
from unittest.mock import Mock

import pytest

from postgres_upgrader.cli import CommandDefinition, CommandRegistry


class TestCommandRegistry:
    """Test CommandRegistry functionality."""

    def test_init_creates_empty_registry(self):
        """Test that a new registry is initialized empty."""
        registry = CommandRegistry()
        assert registry.get_available_commands() == []

    def test_register_single_command(self):
        """Test registering a single command handler."""
        registry = CommandRegistry()
        mock_handler = Mock()

        registry.register("test", mock_handler)

        assert registry.is_registered("test")
        assert registry.get_available_commands() == ["test"]
        assert registry.get_handler("test") is mock_handler

    def test_register_multiple_commands(self):
        """Test registering multiple command handlers."""
        registry = CommandRegistry()
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()

        registry.register("upgrade", handler1)
        registry.register("export", handler2)
        registry.register("import", handler3)

        assert registry.is_registered("upgrade")
        assert registry.is_registered("export")
        assert registry.is_registered("import")
        assert registry.get_available_commands() == [
            "export",
            "import",
            "upgrade",
        ]  # sorted

    def test_register_duplicate_command_raises_error(self):
        """Test that registering a duplicate command raises ValueError."""
        registry = CommandRegistry()
        handler1 = Mock()
        handler2 = Mock()

        registry.register("test", handler1)

        with pytest.raises(ValueError, match=r"Command 'test' is already registered"):
            registry.register("test", handler2)

    def test_get_handler_for_nonexistent_command_raises_error(self):
        """Test that getting handler for unknown command raises ValueError with available commands."""
        registry = CommandRegistry()
        handler1 = Mock()
        handler2 = Mock()

        registry.register("upgrade", handler1)
        registry.register("export", handler2)

        with pytest.raises(
            ValueError,
            match=r"Unknown command 'invalid'\. Available commands: export, upgrade",
        ):
            registry.get_handler("invalid")

    def test_get_handler_empty_registry_raises_error(self):
        """Test that getting handler from empty registry shows no available commands."""
        registry = CommandRegistry()

        with pytest.raises(
            ValueError, match=r"Unknown command 'test'\. Available commands: "
        ):
            registry.get_handler("test")

    def test_is_registered_returns_false_for_unregistered_command(self):
        """Test that is_registered returns False for unregistered commands."""
        registry = CommandRegistry()
        registry.register("test", Mock())

        assert not registry.is_registered("nonexistent")
        assert registry.is_registered("test")

    def test_get_available_commands_returns_sorted_list(self):
        """Test that available commands are returned in sorted order."""
        registry = CommandRegistry()

        # Register in non-alphabetical order
        registry.register("zebra", Mock())
        registry.register("apple", Mock())
        registry.register("banana", Mock())

        commands = registry.get_available_commands()
        assert commands == ["apple", "banana", "zebra"]

    def test_handler_can_be_called_with_args(self):
        """Test that registered handlers can be called with arguments."""
        registry = CommandRegistry()
        mock_handler = Mock()
        mock_args = Mock(spec=argparse.Namespace)

        registry.register("test", mock_handler)
        handler = registry.get_handler("test")
        handler(mock_args)

        mock_handler.assert_called_once_with(mock_args)

    def test_registry_works_with_real_function_handlers(self):
        """Test registry with actual function handlers that match CommandHandler protocol."""
        registry = CommandRegistry()
        call_log = []

        def test_handler(args: argparse.Namespace) -> None:
            call_log.append(f"test called with {args}")

        def upgrade_handler(args: argparse.Namespace) -> None:
            call_log.append(f"upgrade called with {args}")

        registry.register("test", test_handler)
        registry.register("upgrade", upgrade_handler)

        args = argparse.Namespace(command="test")

        # Test that handlers can be retrieved and called
        test_fn = registry.get_handler("test")
        upgrade_fn = registry.get_handler("upgrade")

        test_fn(args)
        upgrade_fn(args)

        assert len(call_log) == 2
        assert "test called" in call_log[0]
        assert "upgrade called" in call_log[1]


class TestCommandDefinition:
    """Test CommandDefinition NamedTuple."""

    def test_command_definition_creation(self):
        """Test creating CommandDefinition instances."""
        handler = Mock()
        cmd_def = CommandDefinition("test", "Test command", handler)

        assert cmd_def.name == "test"
        assert cmd_def.help_text == "Test command"
        assert cmd_def.handler is handler

    def test_command_definition_immutability(self):
        """Test that CommandDefinition is immutable."""
        handler = Mock()
        cmd_def = CommandDefinition("test", "Test command", handler)

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            cmd_def.name = "new_name"  # type: ignore

    def test_command_definition_equality(self):
        """Test CommandDefinition equality comparison."""
        handler1 = Mock()
        handler2 = Mock()

        cmd_def1 = CommandDefinition("test", "Test command", handler1)
        cmd_def2 = CommandDefinition("test", "Test command", handler1)
        cmd_def3 = CommandDefinition("test", "Different help", handler1)
        cmd_def4 = CommandDefinition("test", "Test command", handler2)

        assert cmd_def1 == cmd_def2  # Same values
        assert cmd_def1 != cmd_def3  # Different help_text
        assert cmd_def1 != cmd_def4  # Different handler

    def test_command_definition_can_be_used_with_registry(self):
        """Test that CommandDefinition works seamlessly with CommandRegistry."""
        registry = CommandRegistry()
        handler = Mock()

        cmd_def = CommandDefinition("test", "Test command", handler)
        registry.register(cmd_def.name, cmd_def.handler)

        assert registry.is_registered("test")
        retrieved_handler = registry.get_handler("test")
        assert retrieved_handler is handler


class TestCommandHandlerProtocol:
    """Test CommandHandler Protocol compliance."""

    def test_function_matches_protocol(self):
        """Test that regular functions match CommandHandler protocol."""

        def valid_handler(args: argparse.Namespace) -> None:
            pass

        # This should work without type errors
        registry = CommandRegistry()
        registry.register("test", valid_handler)

        assert registry.is_registered("test")

    def test_callable_class_matches_protocol(self):
        """Test that callable classes match CommandHandler protocol."""

        class CallableHandler:
            def __call__(self, args: argparse.Namespace) -> None:
                self.called_with = args

        handler = CallableHandler()
        registry = CommandRegistry()
        registry.register("test", handler)

        args = argparse.Namespace(test=True)
        retrieved_handler = registry.get_handler("test")
        retrieved_handler(args)

        assert handler.called_with is args
