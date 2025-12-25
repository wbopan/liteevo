#!/usr/bin/env python3
"""Generate MiniWoB task and criteria files for LiteEvolve evolution.

This script works OFFLINE - it does not require a running BrowserGym server.
It uses the gymnasium registry to get the list of available MiniWoB tasks.

Usage:
    python generate_miniwob.py                    # Generate all 125 tasks
    python generate_miniwob.py --limit 10         # Generate first 10 tasks
    python generate_miniwob.py --tasks click-test,enter-text  # Specific tasks
"""

import argparse
from pathlib import Path

# Import to register tasks with gymnasium
import browsergym.miniwob
import gymnasium as gym


def get_all_miniwob_tasks() -> list[str]:
    """Get all MiniWoB task names from gymnasium registry."""
    prefix = "browsergym/miniwob."
    return sorted([
        task_id.replace(prefix, "")
        for task_id in gym.envs.registry.keys()
        if task_id.startswith(prefix)
    ])


def generate_task_files(output_dir: Path, tasks: list[str]) -> None:
    """Generate task_id files in tasks/ directory."""
    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    for i, task_name in enumerate(tasks, 1):
        task_file = tasks_dir / f"{i:03d}_{task_name}.txt"
        task_file.write_text(task_name + "\n")

    print(f"Generated {len(tasks)} task files in {tasks_dir}")


def generate_criteria_files(output_dir: Path, tasks: list[str]) -> None:
    """Generate criteria files in criteria/ directory.

    Each file contains the task_id - the template will wrap it with
    instructions to check /goal and /status responses.
    """
    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)

    for i, task_name in enumerate(tasks, 1):
        criteria_file = criteria_dir / f"{i:03d}_{task_name}.txt"
        # Just the task_id - template will provide evaluation instructions
        criteria_file.write_text(task_name + "\n")

    print(f"Generated {len(tasks)} criteria files in {criteria_dir}")


def generate_task_template(output_dir: Path) -> None:
    """Generate the task template.jinja2."""
    template = '''You are a browser automation agent. Complete the MiniWoB task using curl commands.

## Task: {{ content.strip() }}

## API Endpoint: http://localhost:8000

## Instructions

1. **Reset environment** (initializes your task):
   ```bash
   curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d '{"task": "{{ content.strip() }}"}'
   ```
   This returns the goal and initial axtree.

2. **Get accessibility tree** (shows elements with browser IDs):
   ```bash
   curl http://localhost:8000/axtree
   ```
   The axtree shows elements like `[14] button 'Submit'` - use the number as bid.

3. **Perform actions** using bid from axtree:
   - Click: `curl -X POST http://localhost:8000/click -H "Content-Type: application/json" -d '{"bid": "14"}'`
   - Fill text: `curl -X POST http://localhost:8000/fill -H "Content-Type: application/json" -d '{"bid": "5", "value": "hello"}'`
   - Select option: `curl -X POST http://localhost:8000/select -H "Content-Type: application/json" -d '{"bid": "10", "options": "value"}'`
   - Press key: `curl -X POST http://localhost:8000/keyboard-press -H "Content-Type: application/json" -d '{"key": "Enter"}'`
   - Hover: `curl -X POST http://localhost:8000/hover -H "Content-Type: application/json" -d '{"bid": "8"}'`

4. **Check status** after actions:
   ```bash
   curl http://localhost:8000/status
   ```
   Success when response shows `"reward": 1.0` and `"done": true`.

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /reset | POST | Reset env, optional `{"task": "name"}` body |
| /goal | GET | Get task goal/instruction |
| /axtree | GET | Get accessibility tree with element IDs |
| /status | GET | Check reward and done status |
| /click | POST | Click element `{"bid": "id"}` |
| /fill | POST | Fill input `{"bid": "id", "value": "text"}` |
| /select | POST | Select option `{"bid": "id", "options": "val"}` |
| /keyboard-press | POST | Press key `{"key": "Enter"}` |
| /drag | POST | Drag element `{"from_bid": "a", "to_bid": "b"}` |

## Your Task

Complete the MiniWoB task "{{ content.strip() }}" by:
1. Resetting the environment (the response includes the goal)
2. Observing the axtree to find interactive elements
3. Performing the necessary actions based on the goal
4. Verifying success with /status

**Important:** Explain your reasoning at each step. Output each curl command you execute and its response. End with the final /status response showing the reward.
'''

    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    template_file = tasks_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated task template at {template_file}")


def generate_criteria_template(output_dir: Path) -> None:
    """Generate the criteria template.jinja2."""
    template = '''Task: {{ content.strip() }}

To evaluate whether the agent succeeded at this task:

1. **Check the goal**: The agent should have called `curl http://localhost:8000/goal` or seen the goal in the /reset response.

2. **Check the final status**: Look for the agent's final `curl http://localhost:8000/status` response.
   - **Success**: Response shows `"reward": 1.0` (or close to 1.0) and `"done": true`
   - **Failure**: Response shows `"reward": 0.0` or agent got stuck/errored

3. **Evaluation criteria**:
   - The task is SUCCESSFUL if the agent achieved reward >= 1.0
   - The task FAILED if reward < 1.0 or the agent did not complete the task

Look for the JSON response containing `"reward"` in the agent's output to determine success.
'''

    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)
    template_file = criteria_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated criteria template at {template_file}")


def generate_playbook_schema(output_dir: Path) -> None:
    """Generate a MiniWoB-specific playbook schema."""
    schema = '''{
  "playbook_version": 0,
  "title": "MiniWoB Browser Automation Strategy",
  "description": "Guidance for completing MiniWoB browser tasks via curl API",
  "sections": {
    "workflow": [
      "1. Reset environment with the specific task name",
      "2. Read the goal from the reset response",
      "3. Get axtree to find interactive elements and their bids",
      "4. Identify the target element(s) based on goal keywords",
      "5. Execute actions (click, fill, select) using the bid numbers",
      "6. Check response for reward/done after each action",
      "7. Repeat observe-act cycle until done=true or reward=1.0"
    ],
    "element_identification": [
      "Look for element type (button, textbox, link) in axtree",
      "Match element text/label to goal keywords",
      "Use bid numbers from [N] prefix in axtree output"
    ],
    "common_patterns": [
      "Click buttons: Find button with matching text, use its bid",
      "Fill inputs: Find textbox, use fill endpoint with value from goal",
      "Submit forms: Usually click submit button after filling fields"
    ],
    "error_handling": [
      "If action_error in response, re-check axtree for correct bid",
      "If stuck, try scrolling or looking for hidden elements",
      "If reward stays 0, re-read goal and try different approach"
    ]
  },
  "logs": []
}'''

    schema_file = output_dir / "PLAYBOOK_SCHEMA.txt"
    schema_file.write_text(schema)
    print(f"Generated playbook schema at {schema_file}")


def generate_readme(output_dir: Path) -> None:
    """Generate README.md with usage instructions."""
    readme = '''# MiniWoB Browser Automation Evolution

This example evolves a playbook for completing MiniWoB browser automation tasks.

## Prerequisites

1. **MiniWoB HTML files** must be available at one of:
   - `/tmp/miniwob-plusplus/miniwob/html/miniwob/`
   - `~/miniwob-plusplus/miniwob/html/miniwob/`

   To set up:
   ```bash
   git clone https://github.com/Farama-Foundation/miniwob-plusplus.git /tmp/miniwob-plusplus
   ```

2. **BrowserGym dependencies** (already in pyproject.toml):
   ```bash
   uv sync
   ```

## Generate Task Files

```bash
# Generate all 125 tasks (offline, no server needed)
python examples/miniwob/generate_miniwob.py

# Or generate a subset for testing
python examples/miniwob/generate_miniwob.py --limit 10
```

## Run Evolution

```bash
# Terminal 1: Start BrowserGym server
uv run python -m liteevolve.browsergym_api --dataset miniwob --headless

# Terminal 2: Run evolution
uv run evolve --provider claude \\
  --task-dir examples/miniwob/tasks \\
  --criterion-dir examples/miniwob/criteria \\
  --schema-playbook examples/miniwob/PLAYBOOK_SCHEMA.txt \\
  --step-size 30 \\
  --batch-size 5
```

## How It Works

1. Each task file contains a MiniWoB task ID (e.g., "click-test")
2. The task template renders a full prompt with curl API instructions
3. Claude Code agent executes curl commands against the BrowserGym API
4. Success is determined by the final `/status` response (reward >= 1.0)
5. The playbook evolves to improve task completion strategies

## File Structure

```
examples/miniwob/
├── generate_miniwob.py      # This generator script
├── tasks/
│   ├── template.jinja2      # Task prompt template
│   └── 001_click-test.txt   # Task ID files
├── criteria/
│   ├── template.jinja2      # Evaluation template
│   └── 001_click-test.txt   # Criteria files
├── PLAYBOOK_SCHEMA.txt      # Initial playbook
└── README.md                # This file
```
'''

    readme_file = output_dir / "README.md"
    readme_file.write_text(readme)
    print(f"Generated README at {readme_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate MiniWoB task files for LiteEvolve")
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path(__file__).parent,
        help="Output directory (default: same as script location)"
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Comma-separated list of tasks, or 'all' (default: all)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tasks to generate"
    )

    args = parser.parse_args()

    # Get task list
    all_tasks = get_all_miniwob_tasks()
    print(f"Found {len(all_tasks)} MiniWoB tasks in registry")

    if args.tasks and args.tasks != "all":
        selected = [t.strip() for t in args.tasks.split(",")]
        tasks = [t for t in selected if t in all_tasks]
        if len(tasks) != len(selected):
            missing = set(selected) - set(tasks)
            print(f"Warning: Unknown tasks ignored: {missing}")
    else:
        tasks = all_tasks

    if args.limit:
        tasks = tasks[:args.limit]

    print(f"Generating files for {len(tasks)} MiniWoB tasks...")

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
