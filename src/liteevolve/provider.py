"""Provider implementations for LLM generation."""

import subprocess
from abc import ABC, abstractmethod


class Provider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def __init__(self, args: str | None = None):
        """Initialize the provider.

        Args:
            args: Provider-specific arguments.
        """
        pass

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

    def __init__(self, args: str | None = None):
        """Initialize the Claude Code provider.

        Args:
            args: Optional arguments to pass before -p flag.
        """
        self.args = args

    def generate(self, prompt: str) -> str:
        """Generate a response using Claude Code CLI.

        Args:
            prompt: The input prompt to send to Claude.

        Returns:
            The generated response text.

        Raises:
            RuntimeError: If the Claude CLI command fails.
        """
        cmd = ["claude"]
        if self.args:
            cmd.extend(self.args.split())
        cmd.extend(["-p", prompt])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Claude CLI failed with code {result.returncode}: {result.stderr}"
            )

        return result.stdout


class GeminiProvider(Provider):
    """Provider that uses Gemini CLI for generation."""

    def __init__(self, args: str | None = None):
        """Initialize the Gemini provider.

        Args:
            args: Optional arguments to pass to gemini command.
        """
        self.args = args

    def generate(self, prompt: str) -> str:
        """Generate a response using Gemini CLI.

        Args:
            prompt: The input prompt to send to Gemini.

        Returns:
            The generated response text.

        Raises:
            RuntimeError: If the Gemini CLI command fails.
        """
        cmd = ["gemini"]
        if self.args:
            cmd.extend(self.args.split())
        cmd.append(prompt)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Gemini CLI failed with code {result.returncode}: {result.stderr}"
            )

        return result.stdout


class CLIProvider(Provider):
    """Provider that uses a custom CLI command for generation."""

    def __init__(self, args: str | None = None):
        """Initialize the CLI provider.

        Args:
            args: The CLI command to use for generation (required).
        """
        if not args:
            raise ValueError("args is required for CLIProvider")
        self.args = args

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
            [self.args, prompt],
            capture_output=True,
            text=True,
            shell=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"CLI command '{self.args}' failed with code {result.returncode}: {result.stderr}"
            )

        return result.stdout


def create_provider(name: str, args: str | None = None) -> Provider:
    """Create a provider instance by name.

    Args:
        name: Provider name ("claude", "gemini", or "cli").
        args: Provider-specific arguments.

    Returns:
        The provider instance.

    Raises:
        ValueError: If provider name is unknown or required args missing.
    """
    if name == "claude":
        return ClaudeCodeProvider(args)
    elif name == "gemini":
        return GeminiProvider(args)
    elif name == "cli":
        return CLIProvider(args)
    else:
        raise ValueError(f"Unknown provider: {name}")
