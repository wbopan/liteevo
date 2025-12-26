"""Command-line interface for LiteEvolve."""

import random
from datetime import datetime
from pathlib import Path

import click
import requests
from jinja2 import Environment, BaseLoader
from rich import print
from rich.panel import Panel

from .evolve import EvolutionConfig, load_template, run_evolution
from .provider import create_provider


def fetch_json(url: str) -> dict:
    """Fetch JSON from a URL (GET request).

    Args:
        url: The URL to fetch.

    Returns:
        Parsed JSON response as a dict.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def post_json(url: str, data: dict = None) -> dict:
    """Post JSON to a URL and return response.

    Args:
        url: The URL to post to.
        data: Optional JSON data to send.

    Returns:
        Parsed JSON response as a dict.
    """
    try:
        response = requests.post(url, json=data or {}, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def fetch_text(url: str) -> str:
    """Fetch text content from a URL.

    Args:
        url: The URL to fetch.

    Returns:
        Response text content.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"Error: {e}"


def load_from_directory(dir_path: str) -> list[str]:
    """Load content from files in a directory.

    If template.jinja2 exists, render it for each file with content=file_text.
    Otherwise, return file contents directly.

    Args:
        dir_path: Path to directory containing files.

    Returns:
        List of contents (or rendered templates), sorted by filename.
    """
    directory = Path(dir_path)
    template_path = directory / "template.jinja2"

    # Get all files, excluding .jinja2 files
    files = sorted(
        f for f in directory.iterdir()
        if f.is_file() and not f.suffix == ".jinja2"
    )

    if template_path.exists():
        # Create Jinja2 environment with custom functions
        env = Environment(loader=BaseLoader())
        env.globals["fetch_json"] = fetch_json
        env.globals["post_json"] = post_json
        env.globals["fetch_text"] = fetch_text
        template = env.from_string(template_path.read_text(encoding="utf-8"))
        return [
            template.render(content=f.read_text(encoding="utf-8"))
            for f in files
        ]
    else:
        # Return file contents directly
        return [f.read_text(encoding="utf-8") for f in files]


@click.command()
@click.option(
    "--provider",
    type=click.Choice(["claude", "codex", "gemini", "openai", "cli"]),
    required=True,
    help="The model provider to use.",
)
@click.option(
    "--provider-args",
    type=str,
    default=None,
    help="Arguments for the provider (required if provider=cli).",
)
@click.option(
    "--task",
    type=str,
    default=None,
    help="Single task input string.",
)
@click.option(
    "--task-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Directory containing task files.",
)
@click.option(
    "--criterion",
    type=str,
    default=None,
    help="Single criterion string.",
)
@click.option(
    "--criterion-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Directory containing criterion files.",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Output directory (defaults to outputs/YYYY-MM-DD-HHMMSS/).",
)
@click.option(
    "--name",
    type=str,
    default=None,
    help="Run name (appended to output directory as YYYY-MM-DD-HHMMSS-NAME).",
)
@click.option(
    "--step-size",
    type=int,
    default=10,
    help="Number of evolution steps.",
)
@click.option(
    "--batch-size",
    type=int,
    default=3,
    help="Number of steps per playbook update.",
)
@click.option(
    "--prompt-update-playbook",
    type=click.Path(exists=True),
    default="prompts/UPDATE_PLAYBOOK.jinja2",
    help="Path to playbook update prompt template.",
)
@click.option(
    "--prompt-generate-answer",
    type=click.Path(exists=True),
    default="prompts/GENERATE_ANSWER.jinja2",
    help="Path to generation prompt template.",
)
@click.option(
    "--schema-playbook",
    type=click.Path(exists=True),
    default="prompts/PLAYBOOK_SCHEMA.txt",
    help="Path to playbook schema file.",
)
@click.option(
    "--seed",
    type=int,
    default=42,
    help="Random seed for shuffling tasks (default: 42).",
)
def main(
    provider: str,
    provider_args: str | None,
    task: str | None,
    task_dir: str | None,
    criterion: str | None,
    criterion_dir: str | None,
    output_dir: str | None,
    name: str | None,
    step_size: int,
    batch_size: int,
    prompt_update_playbook: str,
    prompt_generate_answer: str,
    schema_playbook: str,
    seed: int,
) -> None:
    """LiteEvolve - Self-evolution training framework for LLMs.

    Iteratively improve a playbook by having an LLM attempt tasks,
    reflect on failures, and update guidance.
    """
    # Validate provider options
    if provider == "cli" and not provider_args:
        raise click.UsageError("--provider-args is required when provider=cli")

    # Validate task/task_dir options
    if task is None and task_dir is None:
        raise click.UsageError("Either --task or --task-dir must be provided")
    if task is not None and task_dir is not None:
        raise click.UsageError("Cannot use both --task and --task-dir")

    # Validate criterion/criterion_dir options
    if criterion is None and criterion_dir is None:
        raise click.UsageError("Either --criterion or --criterion-dir must be provided")
    if criterion is not None and criterion_dir is not None:
        raise click.UsageError("Cannot use both --criterion and --criterion-dir")

    # Load tasks
    if task is not None:
        task_list = [task]
    else:
        task_list = load_from_directory(task_dir)  # type: ignore
        if not task_list:
            raise click.UsageError(f"No files found in directory: {task_dir}")

    # Load criteria
    if criterion is not None:
        criteria_list = [criterion]
    else:
        criteria_list = load_from_directory(criterion_dir)  # type: ignore
        if not criteria_list:
            raise click.UsageError(f"No files found in directory: {criterion_dir}")

    # Validate matching counts
    if len(task_list) != len(criteria_list):
        raise click.UsageError(
            f"Number of tasks ({len(task_list)}) must match number of criteria ({len(criteria_list)})"
        )

    # Shuffle tasks and criteria together using seed
    rng = random.Random(seed)
    indices = list(range(len(task_list)))
    rng.shuffle(indices)
    task_list = [task_list[i] for i in indices]
    criteria_list = [criteria_list[i] for i in indices]

    # Create provider
    llm_provider = create_provider(provider, provider_args)

    # Create output directories
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        dir_name = f"{timestamp}-{name}" if name else timestamp
        output_dir = f"outputs/{dir_name}"
    output_path = Path(output_dir)
    playbooks_path = output_path / "playbooks"
    generations_path = output_path / "generations"
    inputs_path = output_path / "inputs"
    playbooks_path.mkdir(parents=True, exist_ok=True)
    generations_path.mkdir(parents=True, exist_ok=True)
    inputs_path.mkdir(parents=True, exist_ok=True)

    # Load templates
    generate_template = load_template(prompt_generate_answer)
    update_template = load_template(prompt_update_playbook)

    # Load initial playbook (schema as raw text)
    initial_playbook = Path(schema_playbook).read_text(encoding="utf-8")

    # Create config
    config = EvolutionConfig(
        step_size=step_size,
        batch_size=batch_size,
        playbooks_dir=playbooks_path,
        generations_dir=generations_path,
        inputs_dir=inputs_path,
        generate_template=generate_template,
        update_template=update_template,
    )

    # Print config
    num_batches = (step_size + batch_size - 1) // batch_size
    task_source = task_dir if task_dir else "inline"
    criterion_source = criterion_dir if criterion_dir else "inline"
    config_text = "\n".join([
        f"provider:        {provider}" + (f" ({provider_args})" if provider_args else ""),
        f"tasks:           {len(task_list)} (from {task_source})",
        f"criteria:        {len(criteria_list)} (from {criterion_source})",
        f"seed:            {seed}",
        f"steps:           {step_size}",
        f"batch_size:      {batch_size}",
        f"num_batches:     {num_batches}",
        f"output:          {output_dir}",
        f"gen_template:    {prompt_generate_answer}",
        f"update_template: {prompt_update_playbook}",
        f"schema:          {schema_playbook}",
    ])
    print(Panel(config_text, title="✨ LiteEvolve 🧬", border_style="dim"))

    # Run evolution
    _ = run_evolution(
        provider=llm_provider,
        tasks=task_list,
        criteria=criteria_list,
        initial_playbook=initial_playbook,
        config=config,
    )

    # Print final result
    final_path = playbooks_path / f"playbook_v{num_batches}.txt"
    print(f"\nDone. Final playbook: {final_path}")


if __name__ == "__main__":
    main()
