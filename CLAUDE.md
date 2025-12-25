# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
uv sync                    # Install dependencies
uv run evolve --help       # Show CLI help
uv run evolve --provider claude --task "..." --criterion "..." --step-size 10 --batch-size 3
```

## Architecture

LiteEvolve is a self-evolution framework that improves LLM task performance by iteratively updating a "playbook" (text guidance document) based on task attempts and reflections.

### Core Flow

1. **CLI** (`cli.py`): Parses arguments, loads tasks/criteria from strings or glob patterns, initializes the evolution config
2. **Evolution Loop** (`evolve.py`): Iterates through tasks, generates responses using current playbook, batches results, and triggers playbook updates
3. **Playbook Update**: After `batch_size` steps, sends batch of (task, generation, criterion) to provider with update template; extracts last JSON code block from response

### Key Components

- **Provider** (`provider.py`): Abstract `Provider` base class with `generate(prompt) -> str`. Implementations: `ClaudeCodeProvider`, `OpenAIProvider`, `GeminiProvider`, `CodexProvider`, `CLIProvider`
- **Playbooks**: Raw text strings (not parsed). Schema loaded as text, passed through Jinja2 templates, LLM responses extracted via last code block
- **Templates** (`prompts/`): Jinja2 templates - `GENERATE_ANSWER.jinja2` for generation, `UPDATE_PLAYBOOK.jinja2` for playbook updates, `PLAYBOOK_SCHEMA.txt` as initial playbook

### Output Structure

Outputs go to `outputs/YYYY-MM-DD-HHMMSS/`:
- `playbooks/playbook_v{n}.txt` - Evolved playbook versions
- `generations/{step:03d}_task{task_id:03d}_v{playbook_version}.txt` - Individual generations

### Playbook Extraction

The `extract_playbook_from_response()` function in `evolve.py` uses regex to find the last ` ```json ` or ` ```jsonc ` code block. Failed extractions retry up to `max_retries` times.

### Template Variables

Templates receive: `config`, `step_id`, `tasks`, `generations`, `criteria`, `playbooks`, `current_task`, `current_criterion`, `current_playbook`
