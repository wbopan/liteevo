# AssistantBench Web Research Evolution

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
uv run evolve --provider claude \
  --task-dir examples/assistant_bench/tasks \
  --criterion-dir examples/assistant_bench/criteria \
  --schema-playbook examples/assistant_bench/PLAYBOOK_SCHEMA.txt \
  --step-size 10 \
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
