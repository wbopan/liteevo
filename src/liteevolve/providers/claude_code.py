"""Claude Code CLI provider implementation."""

import subprocess

from .base import Provider


class ClaudeCodeProvider(Provider):
    """Provider that uses Claude Code CLI for generation."""

    def generate(self, prompt: str) -> str:
        """Generate a response using Claude Code CLI.

        Args:
            prompt: The input prompt to send to Claude.

        Returns:
            The generated response text.

        Raises:
            RuntimeError: If the Claude CLI command fails.
        """
        result = subprocess.run(
            ["claude", prompt, "-p"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Claude CLI failed with code {result.returncode}: {result.stderr}"
            )

        return result.stdout
