# BrowserGym Integration

This document covers the BrowserGym browser automation feature in LiteEvolve.

## Overview

[BrowserGym](https://github.com/ServiceNow/BrowserGym) is a gym-style environment for web browser automation, created by ServiceNow. It provides a unified API for multiple browser automation benchmarks.

We expose BrowserGym via a **REST API** (`src/liteevolve/browsergym_api.py`) so LLM agents can interact with browsers using simple `curl` commands.

## Architecture

```
┌─────────────────┐     curl/HTTP      ┌──────────────────────┐
│   LLM Agent     │ ◄────────────────► │  browsergym_api.py   │
│                 │                    │  (FastAPI server)    │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │     BrowserGym       │
                                       │  (Playwright/Chrome) │
                                       └──────────┬───────────┘
                                                  │
                                       ┌──────────┴───────────┐
                                       ▼                      ▼
                               ┌─────────────┐      ┌─────────────────┐
                               │  MiniWoB++  │      │ AssistantBench  │
                               │  (local)    │      │ (real web)      │
                               └─────────────┘      └─────────────────┘
```

## Quick Start

```bash
# Start the REST API server
uv run python -m liteevolve.browsergym_api --dataset miniwob --task click-test --port 8000

# In another terminal, interact via curl
curl -X POST http://localhost:8000/reset
curl http://localhost:8000/axtree
curl -X POST http://localhost:8000/click -H "Content-Type: application/json" -d '{"bid": "13"}'
curl http://localhost:8000/status
```

## Available Benchmarks

### Installed & Ready

| Benchmark | Tasks | Setup | Description |
|-----------|-------|-------|-------------|
| **miniwob** | 125 | Local HTML files | Simple synthetic UI tasks (click, type, drag) |
| **assistantbench** | 215 | None (real web) | Research tasks on live websites |
| **openended** | - | None | Navigate to any URL |

### Requires External Setup

| Benchmark | Tasks | Setup Required | Description |
|-----------|-------|----------------|-------------|
| **webarena** | 812 | 7 Docker containers, 1TB disk, 16GB RAM | Shopping, Reddit, GitLab, Wikipedia |
| **visualwebarena** | 910 | Same as webarena | Visual understanding tasks |
| **workarena** | 19,912 | ServiceNow cloud account (free) | Enterprise software tasks |

## Benchmark Details

### MiniWoB++ (Easy, Local)

Simple synthetic tasks for testing basic agent capabilities.

```bash
uv run python -m liteevolve.browsergym_api --dataset miniwob --task click-test
```

**Example tasks:**
- `click-test`: "Click the button."
- `enter-text`: "Enter 'John' into the text field and press Submit."
- `login-user`: "Enter username 'alice' and password 'pass123' and press login."
- `book-flight`: "Book the shortest one-way flight from Seattle to NYC on 10/23/2016."

**Ground truth:** Not available (procedural validation - checks DOM state)

### AssistantBench (Hard, Real Web)

Complex research tasks on live websites. Starts at Google, agent must navigate and find answers.

```bash
uv run python -m liteevolve.browsergym_api --dataset assistantbench --task validation.3
```

**Example tasks:**
- "What's the lowest price a Single Family house was sold in Queen Anne in January 2023?"
- "Which gyms near Tompkins Square Park (<200m) have fitness classes before 7am?"
- "What is the highest rated Daniel Craig movie <150min available on Netflix US?"

**Ground truth:** Available via `GET /ground-truth` endpoint

### WebArena (Hard, Self-Hosted)

Realistic tasks on self-hosted web applications. Requires significant infrastructure.

**Setup options:**
1. **Official AWS AMI** (fastest): Launch `ami-08a862bf98e3bd7aa` in us-east-2
2. **Unofficial scripts**: https://github.com/gasse/webarena-setup
3. **Single container** (shopping only):
   ```bash
   wget https://archive.org/download/webarena-env-shopping-image/shopping_final_0712.tar
   docker load --input shopping_final_0712.tar
   docker run --name shopping -p 7770:80 -d shopping_final_0712
   ```

**Why self-hosted?** Agents mutate state (buy products, delete repos). Each run needs a clean reset.

## REST API Reference

See [BROWSERGYM_API.md](./BROWSERGYM_API.md) for full endpoint documentation.

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset environment, get initial observation |
| `/close` | POST | Close browser and release resources |
| `/goal` | GET | Get current task instruction |
| `/ground-truth` | GET | Get gold answer (AssistantBench only) |
| `/status` | GET | Check if task is done + reward |
| `/axtree` | GET | Get accessibility tree (element IDs) |
| `/click` | POST | Click element by browser ID |
| `/fill` | POST | Fill text input |
| `/goto` | POST | Navigate to URL |

### Common Workflow

```bash
# 1. Reset environment
curl -X POST http://localhost:8000/reset

# 2. Get accessibility tree to find element IDs
curl http://localhost:8000/axtree

# 3. Perform actions (bid = browser element ID from axtree)
curl -X POST http://localhost:8000/fill \
  -H "Content-Type: application/json" \
  -d '{"bid": "14", "value": "search query"}'

curl -X POST http://localhost:8000/click \
  -H "Content-Type: application/json" \
  -d '{"bid": "15"}'

# 4. Check completion
curl http://localhost:8000/status
# {"reward": 1.0, "done": true, ...}
```

## Evaluation & Ground Truth

### How Validation Works

| Benchmark | Validation Method | Ground Truth |
|-----------|-------------------|--------------|
| **MiniWoB++** | Procedural - checks DOM state | Not available |
| **AssistantBench** | Compare agent's chat answer with gold | Available |
| **WebArena** | SQL queries + DOM checks | Available (needs DB access) |

### AssistantBench Evaluation Flow

1. Agent browses real websites to research the answer
2. Agent sends final answer via **Chat interface**
3. Answer is parsed and compared with gold answer
4. Returns accuracy score (0.0 - 1.0)

**Note:** The Chat window that opens is intentional - it's how agents submit answers for AssistantBench.

### Getting Ground Truth

```bash
# AssistantBench - has ground truth
curl http://localhost:8000/ground-truth
# {"available": true, "answer": "1010000", "task_id": "validation.3"}

# MiniWoB - no ground truth
curl http://localhost:8000/ground-truth
# {"available": false, "answer": null, "task_id": "click-test"}
```

## CLI Options

```bash
uv run python -m liteevolve.browsergym_api [OPTIONS]

Options:
  --dataset, -d    Benchmark name (miniwob, assistantbench, openended, webarena)
  --task, -t       Task name within the benchmark
  --port, -p       Server port (default: 8000)
  --host           Server host (default: 0.0.0.0)
  --headless       Hide browser and chat windows
```

**Environment variables:** `DATASET_NAME`, `TASK_NAME`, `PORT`, `HOST`, `HEADLESS`

## Design Decisions

### Why REST API instead of MCP?

- LLM agents can use `curl` directly without MCP client setup
- Simpler debugging and testing
- Works with any HTTP client

### Why single global environment?

- Simpler state management
- One browser instance at a time
- Matches typical agent workflow

### Why no screenshot endpoint?

- Screenshots add latency and token cost
- Accessibility tree (`/axtree`) provides sufficient info for most tasks
- Can be added later if needed

## Dependencies

```toml
# In pyproject.toml
"browsergym-core>=0.14.2"
"browsergym-miniwob>=0.14.2"
"browsergym-assistantbench>=0.14.2"
"browsergym-webarena>=0.14.2"  # Optional
"fastapi>=0.115.0"
"uvicorn>=0.32.0"
```

## File Structure

```
src/liteevolve/
├── browsergym_api.py    # FastAPI REST server (main file)
├── cli.py
├── evolve.py
└── provider.py

docs/
├── BROWSERGYM.md        # This file
└── BROWSERGYM_API.md    # API endpoint reference
```

## Troubleshooting

### "Environment not initialized"

Call `POST /reset` before any other action endpoints.

### MiniWoB tasks fail to load

Set `MINIWOB_URL` environment variable or ensure files exist at:
- `/tmp/miniwob-plusplus/miniwob/html/miniwob/`
- `~/miniwob-plusplus/miniwob/html/miniwob/`

### Chat window appears

This is expected for AssistantBench - agents submit answers via chat. Use `--headless` to hide all windows.

### numpy array errors

The API handles numpy-to-Python type conversion. If you see errors, check that `active_page_index` is being converted properly.

## Future Improvements

- [ ] Add chat endpoint for AssistantBench answer submission
- [ ] Support multiple concurrent environments (sessions)
- [ ] Add screenshot endpoint (optional)
- [ ] WebSocket support for real-time observation streaming

## References

- [BrowserGym GitHub](https://github.com/ServiceNow/BrowserGym)
- [WebArena Paper (ICLR 2024)](https://arxiv.org/abs/2307.13854)
- [AssistantBench](https://assistantbench.github.io/)
- [MiniWoB++](https://miniwob.farama.org/)
