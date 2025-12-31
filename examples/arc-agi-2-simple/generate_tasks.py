#!/usr/bin/env python3
"""Generate the 100 simplest ARC tasks based on input grid size."""

import json
from pathlib import Path


def calculate_task_complexity(task_data: dict) -> int:
    """Calculate complexity as total cells across all inputs."""
    total_cells = 0
    for example in task_data.get("train", []):
        grid = example.get("input", [])
        total_cells += sum(len(row) for row in grid)
    for test in task_data.get("test", []):
        grid = test.get("input", [])
        total_cells += sum(len(row) for row in grid)
    return total_cells


def main() -> None:
    script_dir = Path(__file__).parent
    # Use data from arc-agi-2 directory
    data_dir = script_dir.parent / "arc-agi-2" / "data" / "ARC-AGI-2" / "data" / "training"
    tasks_dir = script_dir / "tasks"
    criteria_dir = script_dir / "criteria"

    if not data_dir.exists():
        print(f"Data not found at {data_dir}")
        print("Run: cd examples/arc-agi-2 && python generate_arc_tasks.py")
        return

    # Calculate complexity for all tasks
    task_complexities = []
    for json_file in data_dir.glob("*.json"):
        with open(json_file) as f:
            task_data = json.load(f)
        complexity = calculate_task_complexity(task_data)
        task_complexities.append((json_file, task_data, complexity))

    # Sort by complexity (simplest first)
    task_complexities.sort(key=lambda x: x[2])

    # Take 100 simplest
    subset_size = 100
    selected = task_complexities[:subset_size]

    print(f"Complexity range: {selected[0][2]} - {selected[-1][2]} cells")

    # Generate files
    count = 0
    for json_file, task_data, _ in selected:
        task_id = json_file.stem
        train_examples = task_data.get("train", [])
        test_cases = task_data.get("test", [])

        for test_idx, test_case in enumerate(test_cases):
            file_id = f"{task_id}_test{test_idx}" if len(test_cases) > 1 else task_id

            # Task file
            task_content = {
                "train": train_examples,
                "test": {"input": test_case["input"]},
            }
            with open(tasks_dir / f"{file_id}.txt", "w") as f:
                json.dump(task_content, f, separators=(",", ":"))

            # Criterion file
            with open(criteria_dir / f"{file_id}.txt", "w") as f:
                json.dump(test_case["output"], f, separators=(",", ":"))

            count += 1

    print(f"Generated {count} task/criterion pairs in {script_dir}")


if __name__ == "__main__":
    main()
