"""Command-line interface for LiteEvolve."""

from glob import glob
from pathlib import Path

import click

from .evolve import EvolutionConfig, load_template, run_evolution
from .provider import create_provider


def load_tasks_from_glob(pattern: str) -> list[str]:
    """Load task contents from files matching a glob pattern.

    Args:
        pattern: Glob pattern to match task files.

    Returns:
        List of task contents, sorted by filename.
    """
    files = sorted(glob(pattern))
    tasks = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            tasks.append(f.read())
    return tasks


def load_criteria_from_glob(pattern: str) -> list[str]:
    """Load criteria contents from files matching a glob pattern.

    Args:
        pattern: Glob pattern to match criteria files.

    Returns:
        List of criteria contents, sorted by filename.
    """
    files = sorted(glob(pattern))
    criteria = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            criteria.append(f.read())
    return criteria


@click.command()
@click.option(
    "--provider",
    type=click.Choice(["claude", "cli"]),
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
    "--tasks",
    type=str,
    default=None,
    help="Glob pattern for task input files.",
)
@click.option(
    "--criterion",
    type=str,
    default=None,
    help="Single criterion string.",
)
@click.option(
    "--criteria",
    type=str,
    default=None,
    help="Glob pattern for criteria files.",
)
@click.option(
    "--playbooks-dir",
    type=click.Path(),
    default="data/playbooks/",
    help="Output directory for playbooks.",
)
@click.option(
    "--generations-dir",
    type=click.Path(),
    default="data/generations/",
    help="Output directory for generations.",
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
    default="data/prompts/UPDATE_PLAYBOOK.jinja2",
    help="Path to playbook update prompt template.",
)
@click.option(
    "--prompt-generate-answer",
    type=click.Path(exists=True),
    default="data/prompts/GENERATE_ANSWER.jinja2",
    help="Path to generation prompt template.",
)
@click.option(
    "--schema-playbook",
    type=click.Path(exists=True),
    default="data/prompts/PLAYBOOK_SCHEMA.txt",
    help="Path to playbook schema file.",
)
def main(
    provider: str,
    provider_args: str | None,
    task: str | None,
    tasks: str | None,
    criterion: str | None,
    criteria: str | None,
    playbooks_dir: str,
    generations_dir: str,
    step_size: int,
    batch_size: int,
    prompt_update_playbook: str,
    prompt_generate_answer: str,
    schema_playbook: str,
) -> None:
    """LiteEvolve - Self-evolution training framework for LLMs.

    Iteratively improve a playbook by having an LLM attempt tasks,
    reflect on failures, and update guidance.
    """
    # Validate provider options
    if provider == "cli" and not provider_args:
        raise click.UsageError("--provider-args is required when provider=cli")

    # Validate task/tasks options
    if task is None and tasks is None:
        raise click.UsageError("Either --task or --tasks must be provided")
    if task is not None and tasks is not None:
        raise click.UsageError("Cannot use both --task and --tasks")

    # Validate criterion/criteria options
    if criterion is None and criteria is None:
        raise click.UsageError("Either --criterion or --criteria must be provided")
    if criterion is not None and criteria is not None:
        raise click.UsageError("Cannot use both --criterion and --criteria")

    # Load tasks
    if task is not None:
        task_list = [task]
    else:
        task_list = load_tasks_from_glob(tasks)  # type: ignore
        if not task_list:
            raise click.UsageError(f"No files matched pattern: {tasks}")

    # Load criteria
    if criterion is not None:
        criteria_list = [criterion]
    else:
        criteria_list = load_criteria_from_glob(criteria)  # type: ignore
        if not criteria_list:
            raise click.UsageError(f"No files matched pattern: {criteria}")

    # Validate matching counts
    if len(task_list) != len(criteria_list):
        raise click.UsageError(
            f"Number of tasks ({len(task_list)}) must match number of criteria ({len(criteria_list)})"
        )

    # Create provider
    llm_provider = create_provider(provider, provider_args)

    # Create output directories
    playbooks_path = Path(playbooks_dir)
    generations_path = Path(generations_dir)
    playbooks_path.mkdir(parents=True, exist_ok=True)
    generations_path.mkdir(parents=True, exist_ok=True)

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
        generate_template=generate_template,
        update_template=update_template,
    )

    # Run evolution
    _ = run_evolution(
        provider=llm_provider,
        tasks=task_list,
        criteria=criteria_list,
        initial_playbook=initial_playbook,
        config=config,
    )

    # Print final result
    # Calculate final version: number of batches = ceil(step_size / batch_size)
    num_batches = (step_size + batch_size - 1) // batch_size
    final_path = playbooks_path / f"playbook_v{num_batches}.txt"
    print(f"\nEvolution complete. Final playbook saved to: {final_path}")


if __name__ == "__main__":
    main()
