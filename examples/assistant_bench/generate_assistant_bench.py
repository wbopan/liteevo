#!/usr/bin/env python3
"""Generate AssistantBench task and criteria files for LiteEvolve evolution.

This script works OFFLINE - it does not require a running BrowserGym server.
It uses the gymnasium registry to get the list of available AssistantBench tasks.

Usage:
    python generate_assistant_bench.py                    # Generate all validation tasks (33)
    python generate_assistant_bench.py --limit 10         # Generate first 10 tasks
    python generate_assistant_bench.py --split test       # Generate test split instead
"""

import argparse
import importlib
from pathlib import Path

# Import to register tasks with gymnasium
import browsergym.assistantbench
import gymnasium as gym


def get_task_ground_truth(task_name: str) -> str | None:
    """Get ground truth answer for a task by instantiating the task class.

    Args:
        task_name: Task suffix like "validation.0"

    Returns:
        Ground truth answer string, or None if not available
    """
    task_id = f"browsergym/assistantbench.{task_name}"

    if task_id not in gym.envs.registry:
        return None

    entry = gym.envs.registry[task_id]

    # Get the entry point and instantiate task
    entry_point = entry.entry_point
    if callable(entry_point):
        task_class = entry_point
    else:
        module_name, class_name = entry_point.rsplit(":", 1)
        module = importlib.import_module(module_name)
        task_class = getattr(module, class_name)

    # Get task_kwargs from registry entry
    task_kwargs = entry.kwargs.get("task_kwargs", {}) if entry.kwargs else {}

    try:
        task_instance = task_class(**task_kwargs)
        gold = getattr(task_instance, 'gold', None)
        if gold is not None:
            return str(gold)
    except Exception:
        pass

    return None


def get_assistantbench_tasks(split: str = "validation") -> list[str]:
    """Get AssistantBench task names from gymnasium registry.

    Args:
        split: "validation" (33 tasks with answers) or "test" (181 tasks, no answers)

    Returns:
        List of task suffixes like "validation.0", "validation.1", etc.
    """
    prefix = f"browsergym/assistantbench.{split}."
    return sorted([
        task_id.replace("browsergym/assistantbench.", "")
        for task_id in gym.envs.registry.keys()
        if task_id.startswith(prefix)
    ], key=lambda x: int(x.split(".")[-1]))


def generate_task_files(output_dir: Path, tasks: list[str]) -> None:
    """Generate task_id files in tasks/ directory."""
    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    for i, task_name in enumerate(tasks, 1):
        # Extract numeric id for filename
        task_file = tasks_dir / f"{i:03d}_{task_name.replace('.', '_')}.txt"
        task_file.write_text(task_name + "\n")

    print(f"Generated {len(tasks)} task files in {tasks_dir}")


def generate_criteria_files(output_dir: Path, tasks: list[str]) -> None:
    """Generate criteria files in criteria/ directory.

    Each file contains the task_id and ground truth answer (if available).
    Format: task_id|ground_truth_answer
    """
    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)

    tasks_with_gt = 0
    for i, task_name in enumerate(tasks, 1):
        criteria_file = criteria_dir / f"{i:03d}_{task_name.replace('.', '_')}.txt"

        # Get ground truth for this task
        ground_truth = get_task_ground_truth(task_name)
        if ground_truth:
            tasks_with_gt += 1
            # Format: task_id|ground_truth (pipe-separated)
            criteria_file.write_text(f"{task_name}|{ground_truth}\n")
        else:
            criteria_file.write_text(f"{task_name}|\n")

    print(f"Generated {len(tasks)} criteria files in {criteria_dir} ({tasks_with_gt} with ground truth)")


def generate_task_template(output_dir: Path) -> None:
    """Generate the task template.jinja2."""
    template = '''You are a web research agent. Complete the AssistantBench task using curl commands to control a browser.

## Task ID: {{ content.strip() }}

## API Endpoint: http://localhost:8000

## Instructions

1. **Reset environment** (loads your task and shows the goal):
   ```bash
   curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d '{"task": "{{ content.strip() }}"}'
   ```
   This returns the goal (what you need to find) and initial page state.

2. **Navigate the web** to find information:
   ```bash
   curl -X POST http://localhost:8000/goto -H "Content-Type: application/json" -d '{"url": "https://www.google.com"}'
   ```

3. **Get page content** (accessibility tree with element IDs):
   ```bash
   curl http://localhost:8000/axtree
   ```
   Elements show as `[14] button 'Search'` - use the number as bid.

4. **Interact with pages**:
   - Click: `curl -X POST http://localhost:8000/click -H "Content-Type: application/json" -d '{"bid": "14"}'`
   - Fill text: `curl -X POST http://localhost:8000/fill -H "Content-Type: application/json" -d '{"bid": "5", "value": "search query"}'`
   - Press key: `curl -X POST http://localhost:8000/keyboard-press -H "Content-Type: application/json" -d '{"key": "Enter"}'`

5. **Submit your answer** when you have found the information:
   ```bash
   curl -X POST http://localhost:8000/send-message -H "Content-Type: application/json" -d '{"text": "Your answer here"}'
   ```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /reset | POST | Reset env, `{"task": "name"}` body |
| /goal | GET | Get task goal/instruction |
| /axtree | GET | Get accessibility tree with element IDs |
| /goto | POST | Navigate to URL `{"url": "https://..."}` |
| /click | POST | Click element `{"bid": "id"}` |
| /fill | POST | Fill input `{"bid": "id", "value": "text"}` |
| /keyboard-press | POST | Press key `{"key": "Enter"}` |
| /keyboard-type | POST | Type text `{"text": "..."}` |
| /scroll | POST | Scroll page `{"delta_y": 300}` |
| /back | POST | Go back in history |
| /new-tab | POST | Open new tab |
| /send-message | POST | Submit final answer `{"text": "answer"}` |
| /status | GET | Check if task is done |

## Your Task

Complete the AssistantBench task "{{ content.strip() }}" by:
1. Reset the environment to get the goal
2. Navigate the web (use Google, visit relevant sites)
3. Gather information from multiple sources if needed
4. Submit your final answer using /send-message

**Important:**
- Explain your reasoning at each step
- Show each curl command and its response
- When you find the answer, submit it with /send-message
- The answer should be concise and directly answer the question
'''

    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    template_file = tasks_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated task template at {template_file}")


def generate_criteria_template(output_dir: Path) -> None:
    """Generate the criteria template.jinja2.

    The criteria files contain: task_id|ground_truth
    The template parses this and formats the evaluation criterion.
    """
    template = '''{% set parts = content.strip().split('|') %}
{% set task_id = parts[0] %}
{% set ground_truth = parts[1] if parts|length > 1 else '' %}
## Evaluation Criterion for Task: {{ task_id }}

**Ground Truth Answer:** {{ ground_truth if ground_truth else 'Not available' }}

**Success Criteria:**
- The agent's answer (submitted via /send-message) matches or is semantically equivalent to the ground truth above
- Numerical equivalence: "$1,250,000" = "1250000" = "1.25 million"
- Text equivalence: Synonyms and rephrasing are acceptable if meaning is preserved
- List answers: All key items must be present

**Failure Criteria:**
- Agent submitted incorrect information
- Agent failed to find the answer
- Agent did not submit an answer via /send-message
'''

    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)
    template_file = criteria_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated criteria template at {template_file}")


def generate_playbook_schema(output_dir: Path) -> None:
    """Generate an AssistantBench-specific playbook schema."""
    schema = '''{
  "playbook_version": 0,
  "title": "AssistantBench Web Research Strategy",
  "description": "Guidance for completing web research tasks via curl API",
  "sections": {
    "workflow": [
      "1. Reset environment to get the task goal",
      "2. Analyze the goal to identify what information is needed",
      "3. Start with a Google search for relevant queries",
      "4. Navigate to promising search results",
      "5. Extract relevant information from pages (use axtree)",
      "6. Cross-reference information from multiple sources if needed",
      "7. Formulate a concise answer",
      "8. Submit answer using /send-message"
    ],
    "web_navigation": [
      "Use /goto to navigate directly to URLs",
      "Use /click with bid to follow links",
      "Use /fill and /keyboard-press to interact with search forms",
      "Use /scroll to see more content on long pages",
      "Use /back to return to previous pages",
      "Open new tabs for comparing multiple sources"
    ],
    "information_gathering": [
      "Read axtree carefully - it contains all visible text",
      "Look for specific data points mentioned in the goal",
      "Note prices, dates, names, and other factual details",
      "Compare information across multiple sources for accuracy"
    ],
    "answer_formulation": [
      "Answer should directly address the goal question",
      "Be concise - include only the requested information",
      "Use appropriate format (number, name, list, etc.)",
      "Double-check facts before submitting"
    ],
    "error_handling": [
      "If a page fails to load, try an alternative source",
      "If information is outdated, look for more recent sources",
      "If search returns no results, try different keywords",
      "If stuck, step back and reconsider the approach"
    ]
  },
  "logs": []
}'''

    schema_file = output_dir / "PLAYBOOK_SCHEMA.txt"
    schema_file.write_text(schema)
    print(f"Generated playbook schema at {schema_file}")


def generate_readme(output_dir: Path) -> None:
    """Generate README.md with usage instructions."""
    readme = '''# AssistantBench Web Research Evolution

This example evolves a playbook for completing AssistantBench web research tasks.

## Overview

AssistantBench contains 214 realistic web tasks that require:
- Navigating real websites
- Gathering information from multiple sources
- Submitting concise answers

This example uses the **validation split** (33 tasks) which has ground truth answers.

## Prerequisites

1. **BrowserGym with AssistantBench** (already in pyproject.toml):
   ```bash
   uv sync
   ```

## Generate Task Files

```bash
# Generate all 33 validation tasks (offline, no server needed)
python examples/assistant_bench/generate_assistant_bench.py

# Or generate a subset for testing
python examples/assistant_bench/generate_assistant_bench.py --limit 5
```

## Run Evolution

```bash
# Terminal 1: Start BrowserGym server
uv run python -m liteevolve.browsergym_api --dataset assistantbench

# Terminal 2: Run evolution
uv run evolve --provider claude \\
  --task-dir examples/assistant_bench/tasks \\
  --criterion-dir examples/assistant_bench/criteria \\
  --schema-playbook examples/assistant_bench/PLAYBOOK_SCHEMA.txt \\
  --step-size 10 \\
  --batch-size 3
```

## How It Works

1. Each task file contains an AssistantBench task ID (e.g., "validation.0")
2. The task template renders a prompt with curl API instructions
3. The agent navigates real websites to find information
4. Success is determined by comparing the submitted answer to ground truth
5. The playbook evolves to improve web research strategies

## Key Differences from MiniWoB

| Aspect | MiniWoB | AssistantBench |
|--------|---------|----------------|
| Environment | Sandboxed HTML | Real open web |
| Task type | UI interactions | Information gathering |
| Answer submission | Implicit (actions) | Explicit (/send-message) |
| Ground truth | N/A | Via /ground-truth endpoint |
| Evaluation | reward >= 1.0 | Answer comparison |

## File Structure

```
examples/assistant_bench/
├── generate_assistant_bench.py  # Generator script
├── tasks/
│   ├── template.jinja2          # Task prompt template
│   └── 001_validation_0.txt     # Task ID files
├── criteria/
│   ├── template.jinja2          # Evaluation template
│   └── 001_validation_0.txt     # Criteria files
├── PLAYBOOK_SCHEMA.txt          # Initial playbook
└── README.md                    # This file
```
'''

    readme_file = output_dir / "README.md"
    readme_file.write_text(readme)
    print(f"Generated README at {readme_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate AssistantBench task files for LiteEvolve")
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path(__file__).parent,
        help="Output directory (default: same as script location)"
    )
    parser.add_argument(
        "--split",
        type=str,
        default="validation",
        choices=["validation", "test"],
        help="Which split to use (default: validation)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tasks to generate"
    )

    args = parser.parse_args()

    # Get task list
    all_tasks = get_assistantbench_tasks(args.split)
    print(f"Found {len(all_tasks)} AssistantBench {args.split} tasks in registry")

    tasks = all_tasks
    if args.limit:
        tasks = tasks[:args.limit]

    print(f"Generating files for {len(tasks)} AssistantBench tasks...")

    # Generate all files
    generate_task_files(args.output_dir, tasks)
    generate_criteria_files(args.output_dir, tasks)
    generate_task_template(args.output_dir)
    generate_criteria_template(args.output_dir)
    generate_playbook_schema(args.output_dir)
    generate_readme(args.output_dir)

    print(f"\nDone! Run evolution with:")
    print(f"  uv run evolve --provider claude \\")
    print(f"    --task-dir {args.output_dir}/tasks \\")
    print(f"    --criterion-dir {args.output_dir}/criteria \\")
    print(f"    --schema-playbook {args.output_dir}/PLAYBOOK_SCHEMA.txt")


if __name__ == "__main__":
    main()
