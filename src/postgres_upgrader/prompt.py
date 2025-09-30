def prompt_user_choice(choices, prompt_message="Please select an option:"):
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
        # Try to use inquirer for better UX
        import inquirer

        questions = [
            inquirer.List(
                "choice",
                message=prompt_message,
                choices=choices,
            ),
        ]
        answers = inquirer.prompt(questions)
        return answers["choice"] if answers else None

    except (ImportError, KeyboardInterrupt):
        # Fallback to simple text input if inquirer not available or user cancels
        return _simple_text_choice(choices, prompt_message)


def _simple_text_choice(choices, prompt_message="Please select an option:"):
    """
    Fallback text-based choice prompt.

    Args:
        choices: List of strings to choose from
        prompt_message: Message to display to user

    Returns:
        Selected choice string, or None if cancelled
    """
    if not choices:
        return None

    print(f"\n{prompt_message}")
    for i, choice in enumerate(choices, 1):
        print(f"{i}. {choice}")

    while True:
        try:
            selection = input(
                f"\nEnter your choice (1-{len(choices)}, or 'q' to quit): "
            ).strip()

            if selection.lower() == "q":
                return None

            choice_num = int(selection)
            if 1 <= choice_num <= len(choices):
                return choices[choice_num - 1]
            else:
                print(f"Please enter a number between 1 and {len(choices)}")

        except ValueError:
            print("Please enter a valid number or 'q' to quit")
        except KeyboardInterrupt:
            print("\nCancelled by user")
            return None
