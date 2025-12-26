"""
BrowserGym REST API Server

A FastAPI server that exposes BrowserGym's browser automation API for LLM agents.

Usage:
    uv run python -m liteevolve.browsergym_api --dataset miniwob --task click-test --port 8000

    # Or via environment variables
    DATASET_NAME=miniwob TASK_NAME=click-test uv run python -m liteevolve.browsergym_api

API Documentation:
    - Swagger UI: http://localhost:8000/docs
    - OpenAPI spec: http://localhost:8000/openapi.json
    - Agent docs: docs/BROWSERGYM_API.md
"""

import argparse
import os
import sys
from contextlib import asynccontextmanager
from typing import Optional

import gymnasium as gym
import uvicorn
from browsergym.core.action.highlevel import HighLevelActionSet
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# ========== Global State ==========

_env: Optional[gym.Env] = None
_last_obs: Optional[dict] = None
_dataset_name: str = ""
_task_name: str = ""
_headless: bool = False


# ========== Pydantic Models ==========

class ActionResult(BaseModel):
    reward: float = Field(description="Reward from the action")
    terminated: bool = Field(description="Whether the episode terminated")
    truncated: bool = Field(description="Whether the episode was truncated")
    done: bool = Field(description="Whether the episode is done (terminated or truncated)")
    action_error: Optional[str] = Field(default=None, description="Error from the action if any")


class ErrorResponse(BaseModel):
    error: str = Field(description="Error message")


class ResetResponse(BaseModel):
    task_id: str = Field(description="The task ID that was loaded")
    goal: str = Field(description="The task goal/instruction")
    axtree: str = Field(description="Accessibility tree of the page")


class TaskListResponse(BaseModel):
    benchmark: str = Field(description="Benchmark name")
    count: int = Field(description="Number of tasks")
    tasks: list[str] = Field(description="List of task IDs")


class GoalResponse(BaseModel):
    goal: str = Field(description="Current task goal/instruction")


class StatusResponse(BaseModel):
    reward: float = Field(description="Current reward")
    terminated: bool = Field(description="Whether the episode terminated")
    truncated: bool = Field(description="Whether the episode was truncated")
    done: bool = Field(description="Whether the episode is done")
    info: dict = Field(default_factory=dict, description="Additional info")


class PageStateResponse(BaseModel):
    url: str = Field(description="Current page URL")
    open_pages_urls: list[str] = Field(description="URLs of all open pages")
    open_pages_titles: list[str] = Field(description="Titles of all open pages")
    active_page_index: int = Field(description="Index of the active page")


class AxtreeResponse(BaseModel):
    axtree: str = Field(description="Accessibility tree text")


class GroundTruthResponse(BaseModel):
    available: bool = Field(description="Whether ground truth is available for this task")
    answer: Optional[str] = Field(default=None, description="Ground truth answer if available")
    task_id: str = Field(description="Task ID")


class BoundingBox(BaseModel):
    bid: str = Field(description="Browser element ID")
    x: float = Field(description="Left coordinate in pixels")
    y: float = Field(description="Top coordinate in pixels")
    width: float = Field(description="Width in pixels")
    height: float = Field(description="Height in pixels")
    visible: bool = Field(default=True, description="Whether element is visible")
    clickable: bool = Field(default=False, description="Whether element is clickable")
    tag: str = Field(default="", description="HTML tag name")
    text: str = Field(default="", description="Element text content (truncated)")


class BoundingBoxesResponse(BaseModel):
    count: int = Field(description="Number of elements with bounding boxes")
    viewport_width: float = Field(description="Viewport width in pixels")
    viewport_height: float = Field(description="Viewport height in pixels")
    elements: list[BoundingBox] = Field(description="List of elements with bounding boxes")


class MessageResponse(BaseModel):
    status: str = Field(description="Status of the operation")
    message: str = Field(description="The message that was sent or reported")


# Request bodies
class StepRequest(BaseModel):
    action: str = Field(description="BrowserGym action string, e.g., click('a123')")


class ClickRequest(BaseModel):
    bid: str = Field(description="Browser element ID")
    button: str = Field(default="left", description="Mouse button: left, middle, or right")


class HoverRequest(BaseModel):
    bid: str = Field(description="Browser element ID")


class FillRequest(BaseModel):
    bid: str = Field(description="Browser element ID")
    value: str = Field(description="Text to fill")


class PressRequest(BaseModel):
    bid: str = Field(description="Browser element ID")
    key: str = Field(description="Key combination, e.g., Enter, Tab, ControlOrMeta+a")


class FocusRequest(BaseModel):
    bid: str = Field(description="Browser element ID")


class ClearRequest(BaseModel):
    bid: str = Field(description="Browser element ID")


class SelectRequest(BaseModel):
    bid: str = Field(description="Browser element ID of select element")
    options: str = Field(description="Option value(s) to select")


class DragRequest(BaseModel):
    from_bid: str = Field(description="Browser element ID to drag from")
    to_bid: str = Field(description="Browser element ID to drop on")


class MouseMoveRequest(BaseModel):
    x: float = Field(description="X coordinate")
    y: float = Field(description="Y coordinate")


class MouseClickRequest(BaseModel):
    x: float = Field(description="X coordinate")
    y: float = Field(description="Y coordinate")
    button: str = Field(default="left", description="Mouse button: left, middle, or right")


class MouseDragRequest(BaseModel):
    from_x: float = Field(description="Starting X coordinate")
    from_y: float = Field(description="Starting Y coordinate")
    to_x: float = Field(description="Ending X coordinate")
    to_y: float = Field(description="Ending Y coordinate")


class ScrollRequest(BaseModel):
    delta_x: float = Field(default=0, description="Horizontal scroll (positive = right)")
    delta_y: float = Field(default=100, description="Vertical scroll (positive = down)")


class KeyboardPressRequest(BaseModel):
    key: str = Field(description="Key to press, e.g., Enter, Tab, Escape")


class KeyboardTypeRequest(BaseModel):
    text: str = Field(description="Text to type")


class GotoRequest(BaseModel):
    url: str = Field(description="URL to navigate to")


class TabFocusRequest(BaseModel):
    index: int = Field(description="Tab index (0-based)")


class NoopRequest(BaseModel):
    wait_ms: float = Field(default=1000, description="Milliseconds to wait")


class ResetRequest(BaseModel):
    task: Optional[str] = Field(default=None, description="Task name to switch to (e.g., 'click-test')")


class SendMessageRequest(BaseModel):
    text: str = Field(description="Message to send to the user (e.g., final answer for AssistantBench)")


class ReportInfeasibleRequest(BaseModel):
    reason: str = Field(description="Reason why the instructions cannot be followed")


# ========== Helper Functions ==========

def _import_benchmark(dataset: str):
    """Dynamically import the benchmark module to register tasks."""
    if dataset == "miniwob":
        import browsergym.miniwob
    elif dataset == "webarena":
        import browsergym.webarena
    elif dataset == "visualwebarena":
        import browsergym.visualwebarena
    elif dataset == "workarena":
        import browsergym.workarena
    elif dataset == "assistantbench":
        import browsergym.assistantbench
    else:
        import browsergym.core


def _get_axtree_text(obs: dict) -> str:
    """Extract accessibility tree as text from observation."""
    if "axtree_txt" in obs:
        return obs["axtree_txt"]
    if "axtree_object" in obs and obs["axtree_object"]:
        return str(obs["axtree_object"])
    return ""


def _get_bounding_boxes(obs: dict) -> tuple[list[dict], float, float]:
    """Extract bounding boxes from observation.

    Returns:
        Tuple of (elements list, viewport_width, viewport_height)
    """
    elements = []
    viewport_width = 0.0
    viewport_height = 0.0

    # Try to get viewport size from screenshot shape if available
    if "screenshot" in obs and obs["screenshot"] is not None:
        screenshot = obs["screenshot"]
        if hasattr(screenshot, "shape"):
            # Shape is (height, width, channels)
            viewport_height = float(screenshot.shape[0])
            viewport_width = float(screenshot.shape[1])

    # BrowserGym stores element properties in extra_element_properties
    # Format: {bid: {bbox: [x, y, width, height], visible: bool, clickable: bool, ...}}
    extra_props = obs.get("extra_element_properties", {})

    if extra_props:
        for bid, props in extra_props.items():
            if not isinstance(props, dict):
                continue

            bbox = props.get("bbox", props.get("bounding_box", None))
            if bbox is None:
                continue

            # bbox can be [x, y, width, height] or {"x": x, "y": y, "width": w, "height": h}
            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                x, y, width, height = bbox[0], bbox[1], bbox[2], bbox[3]
            elif isinstance(bbox, dict):
                x = bbox.get("x", bbox.get("left", 0))
                y = bbox.get("y", bbox.get("top", 0))
                width = bbox.get("width", 0)
                height = bbox.get("height", 0)
            else:
                continue

            # Get element text (truncate to avoid huge responses)
            text = str(props.get("text", props.get("name", "")))[:100]

            elements.append({
                "bid": str(bid),
                "x": float(x),
                "y": float(y),
                "width": float(width),
                "height": float(height),
                "visible": bool(props.get("visible", True)),
                "clickable": bool(props.get("clickable", False)),
                "tag": str(props.get("tag", props.get("role", ""))),
                "text": text,
            })

    # Fallback: try to extract from axtree_object if extra_element_properties is empty
    if not elements and "axtree_object" in obs and obs["axtree_object"]:
        axtree = obs["axtree_object"]
        elements = _extract_bboxes_from_axtree(axtree)

    return elements, viewport_width, viewport_height


def _extract_bboxes_from_axtree(node, elements=None) -> list[dict]:
    """Recursively extract bounding boxes from accessibility tree object."""
    if elements is None:
        elements = []

    if not isinstance(node, dict):
        return elements

    # Check if this node has bbox info
    bid = node.get("bid", node.get("browsergym_id", None))
    bbox = node.get("bbox", node.get("bounding_box", None))

    if bid is not None and bbox is not None:
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            x, y, width, height = bbox[0], bbox[1], bbox[2], bbox[3]
        elif isinstance(bbox, dict):
            x = bbox.get("x", bbox.get("left", 0))
            y = bbox.get("y", bbox.get("top", 0))
            width = bbox.get("width", 0)
            height = bbox.get("height", 0)
        else:
            x, y, width, height = 0, 0, 0, 0

        text = str(node.get("name", node.get("text", "")))[:100]

        elements.append({
            "bid": str(bid),
            "x": float(x),
            "y": float(y),
            "width": float(width),
            "height": float(height),
            "visible": bool(node.get("visible", True)),
            "clickable": bool(node.get("clickable", False)),
            "tag": str(node.get("role", node.get("tag", ""))),
            "text": text,
        })

    # Recurse into children
    children = node.get("children", [])
    if isinstance(children, list):
        for child in children:
            _extract_bboxes_from_axtree(child, elements)

    return elements


def _check_env_initialized():
    """Raise HTTPException if environment is not initialized."""
    if _env is None:
        raise HTTPException(status_code=400, detail="Environment not initialized. Call POST /reset first.")


def _execute_action(action: str) -> dict:
    """Execute an action and return result."""
    global _env, _last_obs
    _check_env_initialized()

    try:
        obs, reward, terminated, truncated, info = _env.step(action)
        _last_obs = obs

        result = {
            "reward": float(reward),
            "terminated": terminated,
            "truncated": truncated,
            "done": terminated or truncated,
        }

        if "last_action_error" in obs and obs["last_action_error"]:
            result["action_error"] = obs["last_action_error"]

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== App Setup ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup on shutdown
    global _env
    if _env is not None:
        try:
            _env.close()
        except:
            pass


app = FastAPI(
    title="BrowserGym API",
    description="REST API for BrowserGym browser automation",
    version="1.0.0",
    lifespan=lifespan,
)


# ========== Environment Lifecycle ==========

@app.post("/reset", response_model=ResetResponse)
def reset_env(request: ResetRequest = None):
    """Reset the BrowserGym environment and return initial observation.

    Optionally accepts a task name to switch to a different task.
    """
    global _env, _last_obs, _dataset_name, _task_name, _headless

    try:
        # Allow dynamic task switching via request body
        if request and request.task:
            _task_name = request.task

        _import_benchmark(_dataset_name)

        if _dataset_name == "openended" or not _task_name:
            task_id = "browsergym/openended"
        else:
            task_id = f"browsergym/{_dataset_name}.{_task_name}"

        if _env is not None:
            try:
                _env.close()
            except:
                pass

        # Miniwob URL auto-detection
        task_kwargs = {}
        if _dataset_name == "miniwob" and "MINIWOB_URL" not in os.environ:
            miniwob_paths = [
                "/tmp/miniwob-plusplus/miniwob/html/miniwob/",
                os.path.expanduser("~/miniwob-plusplus/miniwob/html/miniwob/"),
            ]
            for path in miniwob_paths:
                if os.path.exists(path):
                    task_kwargs["base_url"] = f"file://{path}"
                    break

        # Create action set with both bid-based and coordinate-based actions
        action_set = HighLevelActionSet(
            subsets=["chat", "infeas", "bid", "coord", "nav", "tab"],
            strict=False,
            multiaction=True,
        )

        if task_kwargs:
            _env = gym.make(
                task_id,
                headless=_headless,
                task_kwargs=task_kwargs,
                action_mapping=action_set.to_python_code,
            )
        else:
            _env = gym.make(
                task_id,
                headless=_headless,
                action_mapping=action_set.to_python_code,
            )
        obs, info = _env.reset()
        _last_obs = obs

        return {
            "task_id": task_id,
            "goal": obs.get("goal", "") or str(obs.get("goal_object", "")),
            "axtree": _get_axtree_text(obs),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/close")
def close_env():
    """Close the BrowserGym environment and release resources."""
    global _env, _last_obs

    if _env is None:
        return {"status": "no environment to close"}

    try:
        _env.close()
        _env = None
        _last_obs = None
        return {"status": "closed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Task Management ==========

@app.get("/tasks/{benchmark}", response_model=TaskListResponse)
def list_tasks(benchmark: str):
    """List all available tasks for a benchmark."""
    try:
        _import_benchmark(benchmark)
        prefix = f"browsergym/{benchmark}"
        task_ids = [
            id.replace("browsergym/", "")
            for id in gym.envs.registry.keys()
            if id.startswith(prefix)
        ]
        return {"benchmark": benchmark, "count": len(task_ids), "tasks": sorted(task_ids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/goal", response_model=GoalResponse)
def get_goal():
    """Get the current task goal/instruction."""
    global _last_obs
    if _last_obs is None:
        raise HTTPException(status_code=400, detail="No observation available. Call POST /reset first.")
    goal = _last_obs.get("goal", "") or str(_last_obs.get("goal_object", ""))
    return {"goal": goal}


@app.get("/ground-truth", response_model=GroundTruthResponse)
def get_ground_truth():
    """Get the ground truth answer for the current task (if available).

    Available for: AssistantBench (has explicit answers)
    Not available for: MiniWoB (procedural validation)
    """
    global _env
    _check_env_initialized()

    task = _env.unwrapped.task
    task_id = getattr(task, 'task_id', '') or getattr(task, 'subdomain', '') or 'unknown'

    # Check for gold answer (AssistantBench)
    gold = getattr(task, 'gold', None)
    if gold is not None:
        return {
            "available": True,
            "answer": str(gold),
            "task_id": str(task_id),
        }

    # No ground truth available (MiniWoB, etc.)
    return {
        "available": False,
        "answer": None,
        "task_id": str(task_id),
    }


@app.get("/ground-truth/{benchmark}/{task}", response_model=GroundTruthResponse)
def get_ground_truth_by_task(benchmark: str, task: str):
    """Get the ground truth answer for a specific task without loading it.

    This endpoint instantiates the task class directly to get the gold answer,
    without starting the browser environment. Useful for evaluation.

    Args:
        benchmark: Benchmark name (assistantbench, miniwob, etc.)
        task: Task name within the benchmark (e.g., validation.0)
    """
    try:
        _import_benchmark(benchmark)

        task_id = f"browsergym/{benchmark}.{task}"

        # Get task entry from gym registry
        if task_id not in gym.envs.registry:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

        entry = gym.envs.registry[task_id]

        # Get the entry point and instantiate task
        entry_point = entry.entry_point
        if callable(entry_point):
            task_class = entry_point
        else:
            import importlib
            module_name, class_name = entry_point.rsplit(":", 1)
            module = importlib.import_module(module_name)
            task_class = getattr(module, class_name)

        # Get task_kwargs from registry entry
        task_kwargs = entry.kwargs.get("task_kwargs", {}) if entry.kwargs else {}

        # Try to instantiate and get gold answer
        try:
            task_instance = task_class(**task_kwargs)

            # Try to get ground truth
            gold = getattr(task_instance, 'gold', None)
            if gold is not None:
                return {
                    "available": True,
                    "answer": str(gold),
                    "task_id": task_id,
                }
        except Exception:
            pass

        # No ground truth available
        return {
            "available": False,
            "answer": None,
            "task_id": task_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status", response_model=StatusResponse)
def check_task_status():
    """Check if the current task is completed."""
    global _env, _last_obs
    _check_env_initialized()

    try:
        obs, reward, terminated, truncated, info = _env.step("noop()")
        _last_obs = obs
        return {
            "reward": float(reward),
            "terminated": terminated,
            "truncated": truncated,
            "done": terminated or truncated,
            "info": {k: str(v) for k, v in info.items()} if info else {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Generic Action ==========

@app.post("/step", response_model=ActionResult)
def step(request: StepRequest):
    """Execute a BrowserGym action string."""
    return _execute_action(request.action)


# ========== BID Element Interaction ==========

@app.post("/click", response_model=ActionResult)
def click(request: ClickRequest):
    """Click an element by its browser ID (bid)."""
    return _execute_action(f"click('{request.bid}', button='{request.button}')")


@app.post("/dblclick", response_model=ActionResult)
def dblclick(request: ClickRequest):
    """Double-click an element by its browser ID."""
    return _execute_action(f"dblclick('{request.bid}', button='{request.button}')")


@app.post("/hover", response_model=ActionResult)
def hover(request: HoverRequest):
    """Hover over an element by its browser ID."""
    return _execute_action(f"hover('{request.bid}')")


@app.post("/fill", response_model=ActionResult)
def fill(request: FillRequest):
    """Fill an input field with text."""
    escaped_value = request.value.replace("'", "\\'")
    return _execute_action(f"fill('{request.bid}', '{escaped_value}')")


@app.post("/press", response_model=ActionResult)
def press(request: PressRequest):
    """Press a key combination on an element."""
    return _execute_action(f"press('{request.bid}', '{request.key}')")


@app.post("/focus", response_model=ActionResult)
def focus(request: FocusRequest):
    """Focus on an element by its browser ID."""
    return _execute_action(f"focus('{request.bid}')")


@app.post("/clear", response_model=ActionResult)
def clear(request: ClearRequest):
    """Clear an input field."""
    return _execute_action(f"clear('{request.bid}')")


@app.post("/select", response_model=ActionResult)
def select_option(request: SelectRequest):
    """Select option(s) in a dropdown."""
    return _execute_action(f"select_option('{request.bid}', '{request.options}')")


@app.post("/drag", response_model=ActionResult)
def drag_and_drop(request: DragRequest):
    """Drag an element and drop it on another element."""
    return _execute_action(f"drag_and_drop('{request.from_bid}', '{request.to_bid}')")


# ========== Coordinate-based Actions ==========

@app.post("/mouse-move", response_model=ActionResult)
def mouse_move(request: MouseMoveRequest):
    """Move mouse to coordinates."""
    return _execute_action(f"mouse_move({request.x}, {request.y})")


@app.post("/mouse-click", response_model=ActionResult)
def mouse_click(request: MouseClickRequest):
    """Click at coordinates."""
    return _execute_action(f"mouse_click({request.x}, {request.y}, button='{request.button}')")


@app.post("/mouse-dblclick", response_model=ActionResult)
def mouse_dblclick(request: MouseClickRequest):
    """Double-click at coordinates."""
    return _execute_action(f"mouse_dblclick({request.x}, {request.y}, button='{request.button}')")


@app.post("/mouse-down", response_model=ActionResult)
def mouse_down(request: MouseClickRequest):
    """Press mouse button at coordinates (without releasing)."""
    return _execute_action(f"mouse_down({request.x}, {request.y}, button='{request.button}')")


@app.post("/mouse-up", response_model=ActionResult)
def mouse_up(request: MouseClickRequest):
    """Release mouse button at coordinates."""
    return _execute_action(f"mouse_up({request.x}, {request.y}, button='{request.button}')")


@app.post("/mouse-drag", response_model=ActionResult)
def mouse_drag(request: MouseDragRequest):
    """Drag from one coordinate to another."""
    return _execute_action(f"mouse_drag_and_drop({request.from_x}, {request.from_y}, {request.to_x}, {request.to_y})")


@app.post("/scroll", response_model=ActionResult)
def scroll(request: ScrollRequest):
    """Scroll the page."""
    return _execute_action(f"scroll({request.delta_x}, {request.delta_y})")


# ========== Keyboard Actions ==========

@app.post("/keyboard-press", response_model=ActionResult)
def keyboard_press(request: KeyboardPressRequest):
    """Press a key."""
    return _execute_action(f"keyboard_press('{request.key}')")


@app.post("/keyboard-type", response_model=ActionResult)
def keyboard_type(request: KeyboardTypeRequest):
    """Type text using keyboard."""
    escaped_text = request.text.replace("'", "\\'")
    return _execute_action(f"keyboard_type('{escaped_text}')")


@app.post("/keyboard-down", response_model=ActionResult)
def keyboard_down(request: KeyboardPressRequest):
    """Press and hold a key."""
    return _execute_action(f"keyboard_down('{request.key}')")


@app.post("/keyboard-up", response_model=ActionResult)
def keyboard_up(request: KeyboardPressRequest):
    """Release a held key."""
    return _execute_action(f"keyboard_up('{request.key}')")


# ========== Navigation ==========

@app.post("/goto", response_model=ActionResult)
def goto(request: GotoRequest):
    """Navigate to a URL."""
    return _execute_action(f"goto('{request.url}')")


@app.post("/back", response_model=ActionResult)
def go_back():
    """Navigate back in browser history."""
    return _execute_action("go_back()")


@app.post("/forward", response_model=ActionResult)
def go_forward():
    """Navigate forward in browser history."""
    return _execute_action("go_forward()")


# ========== Tab Management ==========

@app.post("/new-tab", response_model=ActionResult)
def new_tab():
    """Open a new browser tab."""
    return _execute_action("new_tab()")


@app.post("/close-tab", response_model=ActionResult)
def tab_close():
    """Close the current tab."""
    return _execute_action("tab_close()")


@app.post("/focus-tab", response_model=ActionResult)
def tab_focus(request: TabFocusRequest):
    """Focus on a specific tab by index."""
    return _execute_action(f"tab_focus({request.index})")


# ========== Observation ==========

@app.get("/axtree", response_model=AxtreeResponse)
def get_axtree():
    """Get the accessibility tree of the current page."""
    global _last_obs
    if _last_obs is None:
        raise HTTPException(status_code=400, detail="No observation available. Call POST /reset first.")
    return {"axtree": _get_axtree_text(_last_obs)}


@app.get("/page", response_model=PageStateResponse)
def get_page_state():
    """Get current page state including URL, title, and open tabs."""
    global _last_obs
    if _last_obs is None:
        raise HTTPException(status_code=400, detail="No observation available. Call POST /reset first.")

    # Convert numpy arrays to Python types
    active_idx = _last_obs.get("active_page_index", 0)
    if hasattr(active_idx, "item"):
        active_idx = active_idx.item()
    elif hasattr(active_idx, "__iter__") and not isinstance(active_idx, str):
        active_idx = int(active_idx[0]) if len(active_idx) > 0 else 0

    return {
        "url": _last_obs.get("url", ""),
        "open_pages_urls": list(_last_obs.get("open_pages_urls", [])),
        "open_pages_titles": list(_last_obs.get("open_pages_titles", [])),
        "active_page_index": int(active_idx),
    }


@app.get("/bboxes", response_model=BoundingBoxesResponse)
def get_bounding_boxes():
    """Get bounding boxes for all elements on the page.

    Returns element positions (x, y, width, height) in viewport pixel coordinates.
    Use these coordinates with mouse_click, mouse_drag, etc. for coordinate-based actions.

    Each element includes:
    - bid: Browser element ID (use with /click, /fill, etc.)
    - x, y: Top-left corner coordinates
    - width, height: Element dimensions
    - visible: Whether element is currently visible
    - clickable: Whether element is interactive
    - tag: HTML tag or accessibility role
    - text: Element text content (truncated to 100 chars)
    """
    global _last_obs
    if _last_obs is None:
        raise HTTPException(status_code=400, detail="No observation available. Call POST /reset first.")

    elements, viewport_width, viewport_height = _get_bounding_boxes(_last_obs)

    return {
        "count": len(elements),
        "viewport_width": viewport_width,
        "viewport_height": viewport_height,
        "elements": elements,
    }


# ========== Communication Actions ==========

@app.post("/send-message", response_model=MessageResponse)
def send_message(request: SendMessageRequest):
    """Send a message to the user.

    This is used to submit answers in AssistantBench and similar benchmarks.
    The message is sent to the chat interface where it can be evaluated
    against the ground truth answer.

    Examples:
    - {"text": "Based on my research, the city was founded in 1751."}
    - {"text": "The lowest price for a house in Queen Anne was $1,250,000."}
    """
    _check_env_initialized()

    escaped_text = request.text.replace("'", "\\'")
    result = _execute_action(f"send_msg_to_user('{escaped_text}')")

    return {
        "status": "sent" if not result.get("action_error") else "error",
        "message": request.text,
    }


@app.post("/report-infeasible", response_model=MessageResponse)
def report_infeasible(request: ReportInfeasibleRequest):
    """Report that the current task instructions are infeasible.

    Use this when the task cannot be completed due to missing elements,
    impossible requirements, or other blockers.

    Examples:
    - {"reason": "The email field mentioned in the instructions does not exist on this page."}
    - {"reason": "The website requires login credentials that were not provided."}
    """
    _check_env_initialized()

    escaped_reason = request.reason.replace("'", "\\'")
    result = _execute_action(f"report_infeasible('{escaped_reason}')")

    return {
        "status": "reported" if not result.get("action_error") else "error",
        "message": request.reason,
    }


# ========== Other ==========

@app.post("/noop", response_model=ActionResult)
def noop(request: NoopRequest):
    """Do nothing and wait."""
    return _execute_action(f"noop(wait_ms={request.wait_ms})")


# ========== Main ==========

def main():
    global _dataset_name, _task_name, _headless

    parser = argparse.ArgumentParser(description="BrowserGym REST API Server")
    parser.add_argument("--dataset", "-d",
                        default=os.environ.get("DATASET_NAME", "openended"),
                        help="Dataset/benchmark name (miniwob, webarena, etc.)")
    parser.add_argument("--task", "-t",
                        default=os.environ.get("TASK_NAME", ""),
                        help="Task name within the dataset")
    parser.add_argument("--port", "-p", type=int,
                        default=int(os.environ.get("PORT", "8000")),
                        help="Port to run the server on")
    parser.add_argument("--host",
                        default=os.environ.get("HOST", "0.0.0.0"),
                        help="Host to bind the server to")
    parser.add_argument("--headless", action="store_true",
                        default=os.environ.get("HEADLESS", "").lower() == "true",
                        help="Run browser in headless mode (hides browser and chat windows)")

    args = parser.parse_args()

    _dataset_name = args.dataset
    _task_name = args.task
    _headless = args.headless

    print(f"Starting BrowserGym REST API Server", file=sys.stderr)
    print(f"  Dataset: {_dataset_name}", file=sys.stderr)
    print(f"  Task: {_task_name or '(none)'}", file=sys.stderr)
    print(f"  Headless: {_headless}", file=sys.stderr)
    print(f"  URL: http://{args.host}:{args.port}", file=sys.stderr)
    print(f"  Docs: http://{args.host}:{args.port}/docs", file=sys.stderr)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
