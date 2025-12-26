#!/usr/bin/env python3
"""Generate WorkArena task and criteria files for LiteEvolve evolution.

This script works OFFLINE - it does not require a running BrowserGym server.
It uses the gymnasium registry to get the list of available WorkArena tasks.

Usage:
    python generate_workarena.py                    # Generate all tasks
    python generate_workarena.py --limit 10         # Generate first 10 tasks
    python generate_workarena.py --tasks task1,task2  # Specific tasks
"""

import argparse
from pathlib import Path

# Import to register tasks with gymnasium
import browsergym.workarena
import gymnasium as gym


def get_all_workarena_tasks() -> list[str]:
    """Get all WorkArena task names from gymnasium registry."""
    prefix = "browsergym/workarena."
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
    """Generate criteria files in criteria/ directory."""
    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)

    for i, task_name in enumerate(tasks, 1):
        criteria_file = criteria_dir / f"{i:03d}_{task_name}.txt"
        criteria_file.write_text(task_name + "\n")

    print(f"Generated {len(tasks)} criteria files in {criteria_dir}")


def generate_task_template(output_dir: Path) -> None:
    """Generate the task template.jinja2."""
    template = '''You are a browser automation agent. Complete the WorkArena task {{ content.strip() }} using curl commands.

###DETAILED INSTRUCTION###

## API Endpoint: http://localhost:8000

## Instructions

1. **Reset environment** (initializes your task):
   ```bash
   curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d '{"task": "{{ content.strip() }}"}'
   ```
   Returns: `{"task_id": "...", "goal": "...", "axtree": "..."}`

2. **Get accessibility tree** (shows elements with browser IDs):
   ```bash
   curl http://localhost:8000/axtree
   ```
   The axtree shows elements like `[14] button 'Submit'` - use the number as bid.

3. **Get bounding boxes** (for coordinate-based actions):
   ```bash
   curl http://localhost:8000/bboxes
   ```
   Returns: `{"count": N, "viewport_width": W, "viewport_height": H, "elements": [{"bid": "14", "x": 100, "y": 50, "width": 80, "height": 30, "visible": true, "clickable": true, "tag": "button", "text": "Submit"}, ...]}`

4. **Perform actions** using bid from axtree:
   - Click: `curl -X POST http://localhost:8000/click -H "Content-Type: application/json" -d '{"bid": "14"}'`
   - Fill text: `curl -X POST http://localhost:8000/fill -H "Content-Type: application/json" -d '{"bid": "5", "value": "hello"}'`
   - Select option: `curl -X POST http://localhost:8000/select -H "Content-Type: application/json" -d '{"bid": "10", "options": "value"}'`
   - Press key on element: `curl -X POST http://localhost:8000/press -H "Content-Type: application/json" -d '{"bid": "5", "key": "Enter"}'`
   - Hover: `curl -X POST http://localhost:8000/hover -H "Content-Type: application/json" -d '{"bid": "8"}'`
   - Drag: `curl -X POST http://localhost:8000/drag -H "Content-Type: application/json" -d '{"from_bid": "a", "to_bid": "b"}'`

5. **Coordinate-based actions** (use bboxes to get x,y coordinates):
   - Mouse click: `curl -X POST http://localhost:8000/mouse-click -H "Content-Type: application/json" -d '{"x": 100, "y": 50}'`
   - Mouse drag: `curl -X POST http://localhost:8000/mouse-drag -H "Content-Type: application/json" -d '{"from_x": 10, "from_y": 20, "to_x": 100, "to_y": 200}'`
   - Scroll: `curl -X POST http://localhost:8000/scroll -H "Content-Type: application/json" -d '{"delta_x": 0, "delta_y": 100}'`

6. **Keyboard actions** (global, not element-specific):
   - Press key: `curl -X POST http://localhost:8000/keyboard-press -H "Content-Type: application/json" -d '{"key": "Enter"}'`
   - Type text: `curl -X POST http://localhost:8000/keyboard-type -H "Content-Type: application/json" -d '{"text": "hello world"}'`

7. **Check status** after actions:
   ```bash
   curl http://localhost:8000/status
   ```
   Returns: `{"reward": 0.0, "terminated": false, "truncated": false, "done": false, "info": {}}`
   Success when response shows `"reward": 1.0` and `"done": true`.

## Action Response Format

All action endpoints return:
```json
{
  "reward": 0.0,
  "terminated": false,
  "remaining_steps": 5,
  "truncated": false,
  "done": false,
  "action_error": null
}
```
- `reward`: 1.0 on success, 0.0 otherwise
- `done`: true when task is complete (success or failure)
- `action_error`: error message if action failed, null otherwise

## Available Endpoints

### Environment Lifecycle
| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| /reset | POST | `{"task": "name"}` (optional) | Reset environment, switch task |
| /noop | POST | `{"wait_ms": 1000}` | Do nothing and wait (default: 1000ms) |

### Observation
| Endpoint | Method | Description |
|----------|--------|-------------|
| /goal | GET | Get task goal/instruction |
| /axtree | GET | Get accessibility tree with element IDs (bid) |
| /bboxes | GET | Get bounding boxes with x, y, width, height for all elements |
| /status | GET | Check reward, terminated, truncated, done status |
| /page | GET | Get current URL, open tabs URLs and titles, active tab index |

### BID-based Actions (use element IDs from axtree)
| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| /click | POST | `{"bid": "id", "button": "left"}` | Click element (button: left/middle/right, default: left) |
| /dblclick | POST | `{"bid": "id", "button": "left"}` | Double-click element |
| /fill | POST | `{"bid": "id", "value": "text"}` | Clear and fill input field with text |
| /clear | POST | `{"bid": "id"}` | Clear input field |
| /select | POST | `{"bid": "id", "options": "val"}` | Select option in dropdown |
| /hover | POST | `{"bid": "id"}` | Hover over element |
| /focus | POST | `{"bid": "id"}` | Focus on element |
| /press | POST | `{"bid": "id", "key": "Enter"}` | Focus element and press key |
| /drag | POST | `{"from_bid": "a", "to_bid": "b"}` | Drag element to another element |

### Coordinate-based Actions (use positions from bboxes)
| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| /mouse-click | POST | `{"x": 100, "y": 50, "button": "left"}` | Click at coordinates |
| /mouse-dblclick | POST | `{"x": 100, "y": 50, "button": "left"}` | Double-click at coordinates |
| /mouse-move | POST | `{"x": 100, "y": 50}` | Move mouse to coordinates |
| /mouse-down | POST | `{"x": 100, "y": 50, "button": "left"}` | Press mouse button (without releasing) |
| /mouse-up | POST | `{"x": 100, "y": 50, "button": "left"}` | Release mouse button |
| /mouse-drag | POST | `{"from_x": 10, "from_y": 20, "to_x": 100, "to_y": 200}` | Drag from one point to another |
| /scroll | POST | `{"delta_x": 0, "delta_y": 100}` | Scroll page (positive y = down) |

### Keyboard Actions (global)
| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| /keyboard-press | POST | `{"key": "Enter"}` | Press and release a key |
| /keyboard-type | POST | `{"text": "hello"}` | Type text character by character |
| /keyboard-down | POST | `{"key": "Shift"}` | Press and hold a key |
| /keyboard-up | POST | `{"key": "Shift"}` | Release a held key |

Key names: `Enter`, `Tab`, `Escape`, `Backspace`, `Delete`, `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Home`, `End`, `PageUp`, `PageDown`, `F1`-`F12`, `a`-`z`, `0`-`9`
Modifiers: `Shift`, `Control`, `Alt`, `Meta` (combine with `+`: `Control+a`, `Shift+Enter`)

### Navigation
| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| /goto | POST | `{"url": "https://..."}` | Navigate to URL |
| /back | POST | none | Go back in browser history |
| /forward | POST | none | Go forward in browser history |

### Tab Management
| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| /new-tab | POST | none | Open a new browser tab |
| /close-tab | POST | none | Close current tab |
| /focus-tab | POST | `{"index": 0}` | Focus tab by index (0-based) |

### Communication
| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| /send-message | POST | `{"text": "answer"}` | Submit answer to user (for AssistantBench) |
| /report-infeasible | POST | `{"reason": "why"}` | Report task is impossible |


**Important:** Explain your reasoning at each step. Output each curl command you execute and its response. End with the final /status response and a detailed process log. You are not allowed to use any tool other than curl. No python, no bash scripts
'''

    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    template_file = tasks_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated task template at {template_file}")


def generate_criteria_template(output_dir: Path) -> None:
    """Generate the criteria template.jinja2."""
    template = '''Task: {{ content.strip() }}

Success: The agent achieved reward >= 1.0 and done == true from /status response.
Failure: The agent got reward < 1.0 or did not complete the task.

Look for the final /status JSON response in the agent's output to determine success.
'''

    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)
    template_file = criteria_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated criteria template at {template_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate WorkArena task files for LiteEvolve")
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
    all_tasks = get_all_workarena_tasks()
    print(f"Found {len(all_tasks)} WorkArena tasks in registry")

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

    print(f"Generating files for {len(tasks)} WorkArena tasks...")

    # Generate all files
    generate_task_files(args.output_dir, tasks)
    generate_criteria_files(args.output_dir, tasks)
    generate_task_template(args.output_dir)
    generate_criteria_template(args.output_dir)

    print(f"\nDone! Run evolution with:")
    print(f"  uv run evolve --provider claude \\")
    print(f"    --task-dir {args.output_dir}/tasks \\")
    print(f"    --criterion-dir {args.output_dir}/criteria")


if __name__ == "__main__":
    main()
