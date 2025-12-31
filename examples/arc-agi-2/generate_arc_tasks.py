#!/usr/bin/env python3
"""Generate task and criterion files from ARC-AGI-2 dataset.

This script downloads the ARC-AGI-2 dataset and creates task/criterion pairs
for use with LiteEvolve.
"""

import json
import subprocess
from pathlib import Path


def clone_or_update_repo(repo_url: str, target_dir: Path) -> None:
    """Clone the ARC-AGI-2 repository or update if it exists."""
    if target_dir.exists():
        print(f"Repository already exists at {target_dir}, pulling latest...")
        subprocess.run(["git", "-C", str(target_dir), "pull"], check=True)
    else:
        print(f"Cloning {repo_url} to {target_dir}...")
        subprocess.run(["git", "clone", "--depth", "1", repo_url, str(target_dir)], check=True)


def generate_task_files(
    data_dir: Path,
    tasks_dir: Path,
    criteria_dir: Path,
    dataset: str = "training",
) -> int:
    """Generate task and criterion files from ARC JSON files.

    Args:
        data_dir: Path to the ARC-AGI-2 data directory
        tasks_dir: Output directory for task files
        criteria_dir: Output directory for criterion files
        dataset: Which dataset to use ("training" or "evaluation")

    Returns:
        Number of task files generated
    """
    source_dir = data_dir / dataset
    if not source_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {source_dir}")

    tasks_dir.mkdir(parents=True, exist_ok=True)
    criteria_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for json_file in sorted(source_dir.glob("*.json")):
        with open(json_file) as f:
            task_data = json.load(f)

        task_id = json_file.stem
        train_examples = task_data.get("train", [])
        test_cases = task_data.get("test", [])

        # Handle each test case separately
        for test_idx, test_case in enumerate(test_cases):
            # Create unique ID for tasks with multiple test cases
            if len(test_cases) > 1:
                file_id = f"{task_id}_test{test_idx}"
            else:
                file_id = task_id

            # Task file: contains train examples + test input
            task_content = {
                "train": train_examples,
                "test": {"input": test_case["input"]},
            }

            task_file = tasks_dir / f"{file_id}.txt"
            with open(task_file, "w") as f:
                json.dump(task_content, f, separators=(",", ":"))

            # Criterion file: contains expected output
            criterion_file = criteria_dir / f"{file_id}.txt"
            with open(criterion_file, "w") as f:
                json.dump(test_case["output"], f, separators=(",", ":"))

            count += 1

    return count


def main() -> None:
    """Main entry point."""
    script_dir = Path(__file__).parent
    repo_dir = script_dir / "data" / "ARC-AGI-2"
    tasks_dir = script_dir / "tasks"
    criteria_dir = script_dir / "criteria"

    # Clone or update the repository
    clone_or_update_repo(
        "https://github.com/arcprize/ARC-AGI-2.git",
        repo_dir,
    )

    # Generate task files from training set
    data_dir = repo_dir / "data"
    count = generate_task_files(data_dir, tasks_dir, criteria_dir, "training")
    print(f"Generated {count} task/criterion pairs from training set")

    # Optionally generate from evaluation set
    eval_count = generate_task_files(data_dir, tasks_dir, criteria_dir, "evaluation")
    print(f"Generated {eval_count} task/criterion pairs from evaluation set")

    print(f"\nTotal: {count + eval_count} task/criterion pairs")
    print(f"Tasks directory: {tasks_dir}")
    print(f"Criteria directory: {criteria_dir}")


if __name__ == "__main__":
    main()
