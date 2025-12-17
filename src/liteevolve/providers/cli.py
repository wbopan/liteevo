"""Generic CLI provider implementation."""

import subprocess

from .base import Provider


class CLIProvider(Provider):
    """Provider that uses a custom CLI command for generation."""

    def __init__(self, command: str):
        """Initialize the CLI provider.

        Args:
            command: The CLI command to use for generation.
        """
        self.command = command

    def generate(self, prompt: str) -> str:
        """Generate a response using the configured CLI command.

        The prompt is passed as an argument to the command.

        Args:
            prompt: The input prompt to send to the CLI.

        Returns:
            The generated response text.

        Raises:
            RuntimeError: If the CLI command fails.
        """
        result = subprocess.run(
            [self.command, prompt],
            capture_output=True,
            text=True,
            shell=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"CLI command '{self.command}' failed with code {result.returncode}: {result.stderr}"
            )

        return result.stdout
