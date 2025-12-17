"""Task generation logic using Jinja2 templates."""

from pathlib import Path

from jinja2 import Template

from .providers.base import Provider


def load_template(path: Path | str) -> Template:
    """Load a Jinja2 template from a file.

    Args:
        path: Path to the template file.

    Returns:
        The loaded Jinja2 Template.
    """
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        return Template(f.read())


def generate_for_task(
    provider: Provider,
    task: str,
    playbook: str,
    template: Template,
) -> str:
    """Generate a response for a task using the playbook as context.

    Args:
        provider: The LLM provider to use for generation.
        task: The task input string.
        playbook: The current playbook text for context.
        template: The Jinja2 template for formatting the prompt.

    Returns:
        The generated response text.
    """
    prompt = template.render(
        playbook=playbook,
        task=task,
    )
    return provider.generate(prompt)
