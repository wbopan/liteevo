"""Abstract base class for LLM providers."""

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
