# BrowserGym REST API

REST API for BrowserGym browser automation. Use `curl` to interact with the browser.

## Quick Start

```bash
# Start the server
uv run python -m liteevolve.browsergym_api --dataset miniwob --task click-test --port 8000

# Or with environment variables
DATASET_NAME=miniwob TASK_NAME=click-test uv run python -m liteevolve.browsergym_api
```

**Base URL**: `http://localhost:8000`

## Response Format

All endpoints return JSON. On error, the response includes an `error` field or HTTP 4xx/5xx status.

```json
// Success
{"reward": 0.0, "terminated": false, "truncated": false, "done": false}

// Error
{"detail": "Environment not initialized. Call POST /reset first."}
```

## Common Workflow

```bash
# 1. Reset environment
curl -X POST http://localhost:8000/reset

# 2. Get accessibility tree (find element IDs)
curl http://localhost:8000/axtree

# 3. Perform actions using element IDs (bids)
curl -X POST http://localhost:8000/click -H "Content-Type: application/json" -d '{"bid": "a123"}'

# 4. Check if task is done
curl http://localhost:8000/status

# 5. Close when done
curl -X POST http://localhost:8000/close
```

---

## Environment Lifecycle

### POST /reset

Reset the BrowserGym environment and return initial observation.

```bash
curl -X POST http://localhost:8000/reset
```

Response:
```json
{
  "task_id": "browsergym/miniwob.click-test",
  "goal": "Click the button",
  "axtree": "[1] button 'Click me'"
}
```

### POST /close

Close the environment and release resources.

```bash
curl -X POST http://localhost:8000/close
```

---

## Task Management

### GET /tasks/{benchmark}

List all available tasks for a benchmark.

```bash
curl http://localhost:8000/tasks/miniwob
```

Response:
```json
{
  "benchmark": "miniwob",
  "count": 125,
  "tasks": ["miniwob.click-test", "miniwob.click-button", ...]
}
```

### GET /goal

Get the current task goal/instruction.

```bash
curl http://localhost:8000/goal
```

### GET /ground-truth

Get the ground truth answer for the current task (if available).

- **AssistantBench**: Has explicit answers
- **MiniWoB**: Not available (procedural validation)

```bash
curl http://localhost:8000/ground-truth
```

Response (AssistantBench):
```json
{
  "available": true,
  "answer": "1010000",
  "task_id": "validation.3"
}
```

Response (MiniWoB):
```json
{
  "available": false,
  "answer": null,
  "task_id": "click-test"
}
```

### GET /status

Check if the current task is completed.

```bash
curl http://localhost:8000/status
```

Response:
```json
{
  "reward": 1.0,
  "terminated": true,
  "truncated": false,
  "done": true,
  "info": {}
}
```

---

## Generic Action

### POST /step

Execute a raw BrowserGym action string.

```bash
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"action": "click('\''a123'\'')"}'
```

---

## BID Element Interaction

These endpoints interact with elements using their browser ID (bid) from the accessibility tree.

### POST /click

Click an element by its browser ID.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| bid | string | required | Browser element ID |
| button | string | "left" | Mouse button: left, middle, right |

```bash
curl -X POST http://localhost:8000/click \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123"}'
```

### POST /dblclick

Double-click an element.

```bash
curl -X POST http://localhost:8000/dblclick \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123"}'
```

### POST /hover

Hover over an element.

```bash
curl -X POST http://localhost:8000/hover \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123"}'
```

### POST /fill

Fill an input field with text.

| Field | Type | Description |
|-------|------|-------------|
| bid | string | Browser element ID |
| value | string | Text to fill |

```bash
curl -X POST http://localhost:8000/fill \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123", "value": "Hello world"}'
```

### POST /press

Press a key combination on an element.

| Field | Type | Description |
|-------|------|-------------|
| bid | string | Browser element ID |
| key | string | Key combination: Enter, Tab, ControlOrMeta+a |

```bash
curl -X POST http://localhost:8000/press \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123", "key": "Enter"}'
```

### POST /focus

Focus on an element.

```bash
curl -X POST http://localhost:8000/focus \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123"}'
```

### POST /clear

Clear an input field.

```bash
curl -X POST http://localhost:8000/clear \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123"}'
```

### POST /select

Select option(s) in a dropdown.

| Field | Type | Description |
|-------|------|-------------|
| bid | string | Browser element ID of select |
| options | string | Option value(s) to select |

```bash
curl -X POST http://localhost:8000/select \
  -H "Content-Type: application/json" \
  -d '{"bid": "a123", "options": "option1"}'
```

### POST /drag

Drag an element and drop it on another.

| Field | Type | Description |
|-------|------|-------------|
| from_bid | string | Element to drag |
| to_bid | string | Element to drop on |

```bash
curl -X POST http://localhost:8000/drag \
  -H "Content-Type: application/json" \
  -d '{"from_bid": "a123", "to_bid": "b456"}'
```

---

## Coordinate-based Actions

### POST /mouse-move

Move mouse to coordinates.

```bash
curl -X POST http://localhost:8000/mouse-move \
  -H "Content-Type: application/json" \
  -d '{"x": 100, "y": 200}'
```

### POST /mouse-click

Click at coordinates.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| x | float | required | X coordinate |
| y | float | required | Y coordinate |
| button | string | "left" | Mouse button |

```bash
curl -X POST http://localhost:8000/mouse-click \
  -H "Content-Type: application/json" \
  -d '{"x": 100, "y": 200}'
```

### POST /mouse-dblclick

Double-click at coordinates.

```bash
curl -X POST http://localhost:8000/mouse-dblclick \
  -H "Content-Type: application/json" \
  -d '{"x": 100, "y": 200}'
```

### POST /mouse-down

Press mouse button at coordinates (without releasing).

```bash
curl -X POST http://localhost:8000/mouse-down \
  -H "Content-Type: application/json" \
  -d '{"x": 100, "y": 200}'
```

### POST /mouse-up

Release mouse button at coordinates.

```bash
curl -X POST http://localhost:8000/mouse-up \
  -H "Content-Type: application/json" \
  -d '{"x": 100, "y": 200}'
```

### POST /mouse-drag

Drag from one coordinate to another.

| Field | Type | Description |
|-------|------|-------------|
| from_x | float | Starting X |
| from_y | float | Starting Y |
| to_x | float | Ending X |
| to_y | float | Ending Y |

```bash
curl -X POST http://localhost:8000/mouse-drag \
  -H "Content-Type: application/json" \
  -d '{"from_x": 100, "from_y": 100, "to_x": 200, "to_y": 200}'
```

### POST /scroll

Scroll the page.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| delta_x | float | 0 | Horizontal scroll (positive = right) |
| delta_y | float | 100 | Vertical scroll (positive = down) |

```bash
curl -X POST http://localhost:8000/scroll \
  -H "Content-Type: application/json" \
  -d '{"delta_y": 300}'
```

---

## Keyboard Actions

### POST /keyboard-press

Press a key.

| Field | Type | Description |
|-------|------|-------------|
| key | string | Key: Enter, Tab, Escape, ArrowDown, etc. |

```bash
curl -X POST http://localhost:8000/keyboard-press \
  -H "Content-Type: application/json" \
  -d '{"key": "Enter"}'
```

### POST /keyboard-type

Type text using keyboard.

```bash
curl -X POST http://localhost:8000/keyboard-type \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

### POST /keyboard-down

Press and hold a key.

```bash
curl -X POST http://localhost:8000/keyboard-down \
  -H "Content-Type: application/json" \
  -d '{"key": "Shift"}'
```

### POST /keyboard-up

Release a held key.

```bash
curl -X POST http://localhost:8000/keyboard-up \
  -H "Content-Type: application/json" \
  -d '{"key": "Shift"}'
```

---

## Navigation

### POST /goto

Navigate to a URL.

```bash
curl -X POST http://localhost:8000/goto \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

### POST /back

Navigate back in browser history.

```bash
curl -X POST http://localhost:8000/back
```

### POST /forward

Navigate forward in browser history.

```bash
curl -X POST http://localhost:8000/forward
```

---

## Tab Management

### POST /new-tab

Open a new browser tab.

```bash
curl -X POST http://localhost:8000/new-tab
```

### POST /close-tab

Close the current tab.

```bash
curl -X POST http://localhost:8000/close-tab
```

### POST /focus-tab

Focus on a specific tab by index.

```bash
curl -X POST http://localhost:8000/focus-tab \
  -H "Content-Type: application/json" \
  -d '{"index": 1}'
```

---

## Observation

### GET /axtree

Get the accessibility tree of the current page. The tree contains all interactive elements with their browser IDs (bid).

```bash
curl http://localhost:8000/axtree
```

Response:
```json
{
  "axtree": "[1] RootWebArea 'Page Title'\n  [2] button 'Submit'\n  [3] textbox 'Email'"
}
```

### GET /page

Get current page state including URL and open tabs.

```bash
curl http://localhost:8000/page
```

Response:
```json
{
  "url": "https://example.com",
  "open_pages_urls": ["https://example.com", "https://other.com"],
  "open_pages_titles": ["Example", "Other"],
  "active_page_index": 0
}
```

---

## Other

### POST /noop

Do nothing and wait.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| wait_ms | float | 1000 | Milliseconds to wait |

```bash
curl -X POST http://localhost:8000/noop \
  -H "Content-Type: application/json" \
  -d '{"wait_ms": 2000}'
```
