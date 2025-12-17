"""Main evolution loop for LiteEvolve."""

import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from .provider import Provider


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


@dataclass
class EvolutionConfig:
    """Configuration for the evolution loop."""

    step_size: int
    batch_size: int
    playbooks_dir: Path
    generations_dir: Path
    generate_template: Template
    update_template: Template
    max_retries: int = 5


def generate_with_template(
    provider: Provider,
    template: Template,
    config: EvolutionConfig,
    tasks: list[str],
    generations: list[str],
    criteria: list[str],
    playbooks: list[str],
    step_id: int,
) -> str:
    """Render template with fixed context and generate response.

    Args:
        provider: The LLM provider to use.
        template: The Jinja2 template to render.
        config: Evolution configuration.
        tasks: List of all task input strings.
        generations: List of all generations so far.
        criteria: List of all success criteria strings.
        playbooks: List of all playbook versions.
        step_id: Current step (0-indexed).

    Returns:
        The generated response text.
    """
    prompt = template.render(
        config=config,
        tasks=tasks,
        generations=generations,
        criteria=criteria,
        playbooks=playbooks,
        step_id=step_id,
        current_task=tasks[step_id % len(tasks)],
        current_criterion=criteria[step_id % len(criteria)],
        current_playbook=playbooks[-1],
    )
    return provider.generate(prompt)


def extract_playbook_from_response(text: str) -> str:
    """Extract playbook from LLM response (last json code block or full text)."""
    pattern = r"```(?:json|jsonc)\s*(.*?)\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[-1] if matches else text


def update_playbook(
    provider: Provider,
    config: EvolutionConfig,
    tasks: list[str],
    generations: list[str],
    criteria: list[str],
    playbooks: list[str],
    step_id: int,
) -> tuple[str, str]:
    """Update the playbook based on task results.

    Args:
        provider: The LLM provider to use.
        config: Evolution configuration.
        tasks: List of all task input strings.
        generations: List of all generations so far.
        criteria: List of all success criteria strings.
        playbooks: List of all playbook versions.
        step_id: Current step (0-indexed).

    Returns:
        A tuple of (extracted_playbook, full_response).

    Raises:
        RuntimeError: If playbook extraction fails after max retries.
    """
    last_error = None
    for attempt in range(config.max_retries):
        try:
            response = generate_with_template(
                provider=provider,
                template=config.update_template,
                config=config,
                tasks=tasks,
                generations=generations,
                criteria=criteria,
                playbooks=playbooks,
                step_id=step_id,
            )
            return extract_playbook_from_response(response), response
        except (ValueError, RuntimeError) as e:
            last_error = e
            print(f"Retry {attempt + 1}/{config.max_retries}: {e}")

    raise RuntimeError(
        f"Failed to extract playbook after {config.max_retries} attempts: {last_error}"
    )


def save_playbook(playbook: str, path: Path) -> None:
    """Save a playbook to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(playbook)


def _rel(path: Path) -> str:
    """Get relative path from cwd."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def run_evolution(
    provider: Provider,
    tasks: list[str],
    criteria: list[str],
    initial_playbook: str,
    config: EvolutionConfig,
) -> str:
    """Run the evolution loop.

    Args:
        provider: The LLM provider to use.
        tasks: List of task input strings.
        criteria: List of success criteria strings.
        initial_playbook: The initial/schema playbook text.
        config: Evolution configuration.

    Returns:
        The final evolved playbook as a string.
    """
    playbooks = [initial_playbook]
    all_generations: list[str] = []
    num_batches = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        TextColumn("{task.fields[status]}"),
    ) as progress:
        task = progress.add_task("Evolution", total=config.step_size, status="")

        for step in range(config.step_size):
            task_idx = step % len(tasks)
            current_version = len(playbooks) - 1
            progress.update(task, status=f"task={task_idx} v{current_version}")

            generation = generate_with_template(
                provider=provider,
                template=config.generate_template,
                config=config,
                tasks=tasks,
                generations=all_generations,
                criteria=criteria,
                playbooks=playbooks,
                step_id=step,
            )

            gen_path = config.generations_dir / f"{step:03d}_task{task_idx:03d}_v{current_version}.txt"
            gen_path.parent.mkdir(parents=True, exist_ok=True)
            gen_path.write_text(generation, encoding="utf-8")
            progress.console.print(f"[dim]\\[step={step:03d}/{config.step_size:03d}, task={task_idx}, playbook=v{current_version}] → {_rel(gen_path)}[/]")

            all_generations.append(generation)

            batch_count = len(all_generations) % config.batch_size
            is_batch_full = batch_count == 0
            is_final_step = step == config.step_size - 1

            if is_batch_full or is_final_step:
                num_batches += 1
                batch_size = batch_count if batch_count > 0 else config.batch_size
                progress.console.print(f"[cyan]Updating playbook (batch {num_batches}, {batch_size} samples)...[/]")

                new_playbook, full_response = update_playbook(
                    provider=provider,
                    config=config,
                    tasks=tasks,
                    generations=all_generations,
                    criteria=criteria,
                    playbooks=playbooks,
                    step_id=step,
                )

                new_version = len(playbooks)
                playbook_path = config.playbooks_dir / f"playbook_v{new_version}.txt"
                save_playbook(new_playbook, playbook_path)
                update_gen_path = config.generations_dir / f"playbook_v{new_version}.txt"
                update_gen_path.write_text(full_response, encoding="utf-8")
                progress.console.print(f"[green]✓ {_rel(update_gen_path)}[/]")


                playbooks.append(new_playbook)

            progress.advance(task)

    return playbooks[-1]
