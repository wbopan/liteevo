# MiniWoB Browser Automation Evolution

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
uv run evolve --provider claude \
  --task-dir examples/miniwob/tasks \
  --criterion-dir examples/miniwob/criteria \
  --schema-playbook examples/miniwob/PLAYBOOK_SCHEMA.txt \
  --step-size 30 \
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
