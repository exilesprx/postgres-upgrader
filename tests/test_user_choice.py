"""
Tests for user choice functionality with inquirer.
"""

from unittest.mock import patch
from postgres_upgrader import prompt_user_choice


class TestInquirerChoice:
    """Test inquirer functionality."""

    def test_prompt_user_choice_with_inquirer(self):
        """Test that inquirer is used when available."""
        choices = ["Option 1", "Option 2", "Option 3"]

        # Mock inquirer directly since it's now imported at module level
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = {"choice": "Option 2"}

            result = prompt_user_choice(choices, "Test prompt")
            assert result == "Option 2"

    def test_prompt_user_choice_inquirer_cancelled(self):
        """Test inquirer returning None (user cancelled)."""
        choices = ["Option 1", "Option 2"]

        # Mock inquirer directly
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.return_value = None  # User cancelled

            result = prompt_user_choice(choices, "Test prompt")
            assert result is None

    def test_fallback_on_keyboard_interrupt(self):
        """Test that KeyboardInterrupt returns None (user cancellation)."""
        choices = ["Option 1", "Option 2"]

        # Mock inquirer to raise KeyboardInterrupt
        with patch("postgres_upgrader.prompt.inquirer") as mock_inquirer:
            mock_inquirer.List.return_value = "mock_question"
            mock_inquirer.prompt.side_effect = KeyboardInterrupt()

            result = prompt_user_choice(choices, "Test prompt")
            assert result is None


class TestEdgeCases:
    """Test edge cases."""

    def test_prompt_user_choice_empty_list(self):
        """Test with empty choices list."""
        result = prompt_user_choice([], "Test prompt")
        assert result is None
