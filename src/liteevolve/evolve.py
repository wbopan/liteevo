"""Main evolution loop for LiteEvolve."""

import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Template

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
    all_generations: list[str] = []
    num_batches = 0

    print(f"Starting evolution: {config.step_size} steps, batch size {config.batch_size}")
    print(f"Tasks: {len(tasks)}, Criteria: {len(criteria)}")

    for step in range(config.step_size):
        task_idx = step % len(tasks)
        current_version = len(playbooks) - 1

        print(f"Step {step + 1}/{config.step_size} (task {task_idx})")

        # Generate response for this task
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

        # Save generation
        save_generation(
            generation=generation,
            step=step,
            task_id=task_idx,
            playbook_version=current_version,
            generations_dir=config.generations_dir,
        )

        # Add to all generations
        all_generations.append(generation)

        # Update playbook when batch is full or at final step
        batch_count = len(all_generations) % config.batch_size
        is_batch_full = batch_count == 0
        is_final_step = step == config.step_size - 1

        if is_batch_full or is_final_step:
            num_batches += 1
            batch_size = batch_count if batch_count > 0 else config.batch_size
            print(f"  Updating playbook (batch {num_batches}, {batch_size} samples)")

            new_playbook, full_response = update_playbook(
                provider=provider,
                config=config,
                tasks=tasks,
                generations=all_generations,
                criteria=criteria,
                playbooks=playbooks,
                step_id=step,
            )

            # Save new playbook
            new_version = len(playbooks)
            playbook_path = config.playbooks_dir / f"playbook_v{new_version}.txt"
            save_playbook(new_playbook, playbook_path)
            print(f"  Saved playbook v{new_version} to {playbook_path}")

            # Save full generation from playbook update
            update_gen_path = config.generations_dir / f"v{new_version}_playbook.txt"
            with open(update_gen_path, "w", encoding="utf-8") as f:
                f.write(full_response)
            print(f"  Saved playbook update generation to {update_gen_path}")

            playbooks.append(new_playbook)

    return playbooks[-1]
