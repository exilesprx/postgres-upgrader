"""
Tests for user choice functionality with inquirer and text fallback.
"""
import pytest
from unittest.mock import patch, MagicMock
from postgres_upgrader import prompt_user_choice
from postgres_upgrader.prompt import _simple_text_choice


class TestInquirerChoice:
    """Test inquirer functionality."""
    
    def test_prompt_user_choice_with_inquirer(self):
        """Test that inquirer is used when available."""
        choices = ["Option 1", "Option 2", "Option 3"]
        
        # Mock the import of inquirer within the function
        mock_inquirer = MagicMock()
        mock_inquirer.List.return_value = "mock_question"
        mock_inquirer.prompt.return_value = {'choice': 'Option 2'}
        
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'inquirer':
                    return mock_inquirer
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            result = prompt_user_choice(choices, "Test prompt")
            assert result == "Option 2"
    
    def test_prompt_user_choice_inquirer_cancelled(self):
        """Test inquirer returning None (user cancelled)."""
        choices = ["Option 1", "Option 2"]
        
        mock_inquirer = MagicMock()
        mock_inquirer.List.return_value = "mock_question"
        mock_inquirer.prompt.return_value = None  # User cancelled
        
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'inquirer':
                    return mock_inquirer
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            result = prompt_user_choice(choices, "Test prompt")
            assert result is None


class TestTextFallback:
    """Test text fallback functionality."""
    
    def test_fallback_when_inquirer_not_available(self):
        """Test fallback to text input when inquirer import fails."""
        choices = ["Option 1", "Option 2", "Option 3"]
        
        # Mock import to raise ImportError for inquirer
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'inquirer':
                    raise ImportError("No module named 'inquirer'")
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            with patch('builtins.input', return_value='2'):
                result = prompt_user_choice(choices, "Test prompt")
                assert result == "Option 2"
    
    def test_fallback_on_keyboard_interrupt(self):
        """Test fallback when inquirer raises KeyboardInterrupt."""
        choices = ["Option 1", "Option 2"]
        
        mock_inquirer = MagicMock()
        mock_inquirer.List.return_value = "mock_question"
        mock_inquirer.prompt.side_effect = KeyboardInterrupt()
        
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'inquirer':
                    return mock_inquirer
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            with patch('builtins.input', return_value='1'):
                result = prompt_user_choice(choices, "Test prompt")
                assert result == "Option 1"


class TestSimpleTextChoice:
    """Test the simple text choice function directly."""
    
    def test_simple_text_choice_valid_selection(self):
        """Test valid user selection in text mode."""
        choices = ["Option 1", "Option 2", "Option 3"]
        
        with patch('builtins.input', return_value='2'):
            result = _simple_text_choice(choices, "Test prompt")
            assert result == "Option 2"
    
    def test_simple_text_choice_quit(self):
        """Test user quitting in text mode."""
        choices = ["Option 1", "Option 2"]
        
        with patch('builtins.input', return_value='q'):
            result = _simple_text_choice(choices, "Test prompt")
            assert result is None
    
    def test_simple_text_choice_invalid_then_valid(self):
        """Test invalid input followed by valid input in text mode."""
        choices = ["Option 1", "Option 2"]
        
        # First invalid (out of range), then valid
        with patch('builtins.input', side_effect=['5', '1']):
            result = _simple_text_choice(choices, "Test prompt")
            assert result == "Option 1"
    
    def test_simple_text_choice_keyboard_interrupt(self):
        """Test KeyboardInterrupt handling in text mode."""
        choices = ["Option 1", "Option 2"]
        
        with patch('builtins.input', side_effect=KeyboardInterrupt()):
            result = _simple_text_choice(choices, "Test prompt")
            assert result is None
    
    def test_simple_text_choice_empty_list(self):
        """Test simple text choice with empty list."""
        result = _simple_text_choice([], "Test prompt")
        assert result is None


class TestEdgeCases:
    """Test edge cases for both modes."""
    
    def test_prompt_user_choice_empty_list(self):
        """Test with empty choices list."""
        result = prompt_user_choice([], "Test prompt")
        assert result is None