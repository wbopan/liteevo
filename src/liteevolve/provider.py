"""Provider implementations for LLM generation."""

import os
import subprocess
from abc import ABC, abstractmethod

from openai import OpenAI


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


class CodexProvider(Provider):
    """Provider that uses Codex CLI for generation."""

    def __init__(self, args: str | None = None):
        """Initialize the Codex provider.

        Args:
            args: Optional arguments to pass to codex exec command.
        """
        self.args = args

    def generate(self, prompt: str) -> str:
        """Generate a response using Codex CLI.

        Args:
            prompt: The input prompt to send to Codex.

        Returns:
            The generated response text.

        Raises:
            RuntimeError: If the Codex CLI command fails.
        """
        cmd = ["codex", "exec"]
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
                f"Codex CLI failed with code {result.returncode}: {result.stderr}"
            )

        return result.stdout


class OpenAIProvider(Provider):
    """Provider that uses OpenAI-compatible API for generation."""

    def __init__(self, args: str | None = None):
        """Initialize the OpenAI provider.

        Args:
            args: Comma-separated key=value pairs for configuration.
                  Supported keys: model (required), base_url, api_key, temperature.
        """
        params = {}
        if args:
            for pair in args.split(","):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    params[key.strip()] = value.strip()

        if "model" not in params:
            raise ValueError("model is required for OpenAIProvider (e.g., model=gpt-4)")

        self.model = params["model"]
        self.base_url = params.get("base_url", "https://api.openai.com/v1")
        self.api_key = params.get("api_key") or os.environ.get("OPENAI_API_KEY")
        self.temperature = float(params.get("temperature", "0.7"))

        if not self.api_key:
            raise ValueError(
                "api_key is required for OpenAIProvider "
                "(pass api_key=... or set OPENAI_API_KEY env var)"
            )

    def generate(self, prompt: str) -> str:
        """Generate a response using OpenAI-compatible API.

        Args:
            prompt: The input prompt to send to the model.

        Returns:
            The generated response text.

        Raises:
            RuntimeError: If the API request fails.
        """
        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
        )
        return response.choices[0].message.content


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
        name: Provider name ("claude", "codex", "gemini", "openai", or "cli").
        args: Provider-specific arguments.

    Returns:
        The provider instance.

    Raises:
        ValueError: If provider name is unknown or required args missing.
    """
    if name == "claude":
        return ClaudeCodeProvider(args)
    elif name == "codex":
        return CodexProvider(args)
    elif name == "gemini":
        return GeminiProvider(args)
    elif name == "openai":
        return OpenAIProvider(args)
    elif name == "cli":
        return CLIProvider(args)
    else:
        raise ValueError(f"Unknown provider: {name}")
