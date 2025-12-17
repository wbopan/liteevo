"""Main evolution loop for LiteEvolve."""

import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template

from .generate import generate_for_task, load_template
from .providers.base import Provider


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


@dataclass
class BatchItem:
    """A single item in a batch for playbook updates."""

    task: str
    generation: str
    criterion: str
    task_id: int


def extract_playbook_from_response(text: str) -> str:
    """Extract playbook from LLM response (last code block or full text)."""
    pattern = r"```(?:json|jsonc)?\s*(.*?)\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    return matches[-1] if matches else text


def update_playbook(
    provider: Provider,
    batch: list[BatchItem],
    playbooks: list[str],
    config: EvolutionConfig,
) -> str:
    """Update the playbook based on a batch of task results.

    Args:
        provider: The LLM provider to use.
        batch: List of batch items with tasks, generations, and criteria.
        playbooks: List of all playbook versions as strings.
        config: Evolution configuration.

    Returns:
        The updated playbook as a string.

    Raises:
        RuntimeError: If playbook extraction fails after max retries.
    """
    prompt = config.update_template.render(
        step_size=config.step_size,
        batch_size=len(batch),
        tasks=[item.task for item in batch],
        generations=[item.generation for item in batch],
        criteria=[item.criterion for item in batch],
        playbook_latest_version=len(playbooks) - 1,
        playbooks=playbooks,
    )

    # Try to get valid playbook with retries
    last_error = None
    for attempt in range(config.max_retries):
        try:
            response = provider.generate(prompt)
            return extract_playbook_from_response(response)
        except (ValueError, RuntimeError) as e:
            last_error = e
            print(f"  Retry {attempt + 1}/{config.max_retries}: {e}")

    raise RuntimeError(
        f"Failed to extract playbook after {config.max_retries} attempts: {last_error}"
    )


def save_generation(
    generation: str,
    step: int,
    task_id: int,
    playbook_version: int,
    generations_dir: Path,
) -> None:
    """Save a generation to disk.

    Args:
        generation: The generated text.
        step: Current step number.
        task_id: The task ID.
        playbook_version: The playbook version used.
        generations_dir: Directory to save generations.
    """
    generations_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{step:03d}_task{task_id:03d}_v{playbook_version}.txt"
    path = generations_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(generation)


def save_playbook(playbook: str, path: Path) -> None:
    """Save a playbook to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(playbook)


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
    # Initialize
    playbooks = [initial_playbook]
    batch_buffer: list[BatchItem] = []
    num_batches = 0

    print(f"Starting evolution: {config.step_size} steps, batch size {config.batch_size}")
    print(f"Tasks: {len(tasks)}, Criteria: {len(criteria)}")

    for step in range(config.step_size):
        task_idx = step % len(tasks)
        task = tasks[task_idx]
        criterion = criteria[task_idx]
        current_playbook = playbooks[-1]
        current_version = len(playbooks) - 1

        print(f"Step {step + 1}/{config.step_size} (task {task_idx})")

        # Generate response for this task
        generation = generate_for_task(
            provider=provider,
            task=task,
            playbook=current_playbook,
            template=config.generate_template,
        )

        # Save generation
        save_generation(
            generation=generation,
            step=step,
            task_id=task_idx,
            playbook_version=current_version,
            generations_dir=config.generations_dir,
        )

        # Add to batch
        batch_buffer.append(
            BatchItem(
                task=task,
                generation=generation,
                criterion=criterion,
                task_id=task_idx,
            )
        )

        # Update playbook when batch is full or at final step
        is_batch_full = len(batch_buffer) >= config.batch_size
        is_final_step = step == config.step_size - 1

        if is_batch_full or is_final_step:
            num_batches += 1
            print(f"  Updating playbook (batch {num_batches}, {len(batch_buffer)} samples)")

            new_playbook = update_playbook(
                provider=provider,
                batch=batch_buffer,
                playbooks=playbooks,
                config=config,
            )

            # Save new playbook
            new_version = len(playbooks)
            playbook_path = config.playbooks_dir / f"playbook_v{new_version}.txt"
            save_playbook(new_playbook, playbook_path)
            print(f"  Saved playbook v{new_version} to {playbook_path}")

            playbooks.append(new_playbook)
            batch_buffer = []

    return playbooks[-1]
