"""Provider implementations for LLM generation."""

import subprocess
from abc import ABC, abstractmethod


class Provider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a response for the given prompt.

        Args:
            prompt: The input prompt to send to the LLM.

        Returns:
            The generated response text.
        """
        pass


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


def create_provider(name: str, args: str | None = None) -> Provider:
    """Create a provider instance by name.

    Args:
        name: Provider name ("claude" or "cli").
        args: Provider arguments (required for "cli").

    Returns:
        The provider instance.

    Raises:
        ValueError: If provider name is unknown or args missing for cli.
    """
    if name == "claude":
        return ClaudeCodeProvider()
    elif name == "cli":
        if not args:
            raise ValueError("args is required for cli provider")
        return CLIProvider(args)
    else:
        raise ValueError(f"Unknown provider: {name}")
