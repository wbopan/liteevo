#!/usr/bin/env python3
"""Generate a subset of simpler ARC tasks based on input grid size.

Simpler tasks are defined as those with smaller total input cells
(sum of all cells across train examples + test input).
"""

import json
import shutil
from pathlib import Path


def calculate_task_complexity(task_data: dict) -> int:
    """Calculate complexity as total cells across all inputs.

    Args:
        task_data: The parsed task JSON.

    Returns:
        Total number of cells in all input grids.
    """
    total_cells = 0

    # Count cells in training examples
    for example in task_data.get("train", []):
        grid = example.get("input", [])
        total_cells += sum(len(row) for row in grid)

    # Count cells in test inputs
    for test in task_data.get("test", []):
        grid = test.get("input", [])
        total_cells += sum(len(row) for row in grid)

    return total_cells


def generate_simple_subset(
    data_dir: Path,
    output_tasks_dir: Path,
    output_criteria_dir: Path,
    subset_size: int = 200,
    dataset: str = "training",
) -> int:
    """Generate a subset of simpler tasks.

    Args:
        data_dir: Path to ARC-AGI-2 data directory
        output_tasks_dir: Output directory for task files
        output_criteria_dir: Output directory for criterion files
        subset_size: Number of tasks to include
        dataset: Which dataset to use

    Returns:
        Number of task files generated
    """
    source_dir = data_dir / dataset
    if not source_dir.exists():
        raise FileNotFoundError(f"Dataset not found: {source_dir}")

    # Calculate complexity for all tasks
    task_complexities = []
    for json_file in source_dir.glob("*.json"):
        with open(json_file) as f:
            task_data = json.load(f)
        complexity = calculate_task_complexity(task_data)
        task_complexities.append((json_file, task_data, complexity))

    # Sort by complexity (simplest first)
    task_complexities.sort(key=lambda x: x[2])

    # Print complexity distribution
    complexities = [c for _, _, c in task_complexities]
    print(f"Complexity distribution (total input cells):")
    print(f"  Min: {min(complexities)}, Max: {max(complexities)}")
    print(f"  Selected range: {complexities[0]} - {complexities[subset_size-1]}")

    # Clear output directories (but keep template)
    for f in output_tasks_dir.glob("*.txt"):
        f.unlink()
    for f in output_criteria_dir.glob("*.txt"):
        f.unlink()

    # Generate files for simplest tasks
    count = 0
    for json_file, task_data, complexity in task_complexities[:subset_size]:
        task_id = json_file.stem
        train_examples = task_data.get("train", [])
        test_cases = task_data.get("test", [])

        for test_idx, test_case in enumerate(test_cases):
            if len(test_cases) > 1:
                file_id = f"{task_id}_test{test_idx}"
            else:
                file_id = task_id

            # Task file
            task_content = {
                "train": train_examples,
                "test": {"input": test_case["input"]},
            }
            task_file = output_tasks_dir / f"{file_id}.txt"
            with open(task_file, "w") as f:
                json.dump(task_content, f, separators=(",", ":"))

            # Criterion file
            criterion_file = output_criteria_dir / f"{file_id}.txt"
            with open(criterion_file, "w") as f:
                json.dump(test_case["output"], f, separators=(",", ":"))

            count += 1

    return count


def main() -> None:
    script_dir = Path(__file__).parent
    data_dir = script_dir / "data" / "ARC-AGI-2" / "data"
    tasks_dir = script_dir / "tasks"
    criteria_dir = script_dir / "criteria"

    if not data_dir.exists():
        print("ARC-AGI-2 data not found. Run generate_arc_tasks.py first.")
        return

    count = generate_simple_subset(
        data_dir,
        tasks_dir,
        criteria_dir,
        subset_size=200,
        dataset="training",
    )

    print(f"\nGenerated {count} simple task/criterion pairs")
    print(f"Tasks: {tasks_dir}")
    print(f"Criteria: {criteria_dir}")


if __name__ == "__main__":
    main()
