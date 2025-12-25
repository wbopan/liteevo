"""
BrowserGym MCP Server

A Model Context Protocol server that exposes BrowserGym's browser automation API.

Usage:
    uv run mcp_browsergym.py --dataset miniwob --task click-test

    # Or via environment variables
    DATASET_NAME=miniwob TASK_NAME=click-test uv run mcp_browsergym.py

Test with MCP Inspector:
    npx @modelcontextprotocol/inspector uv run mcp_browsergym.py --dataset miniwob --task click-test
"""

import argparse
import base64
import io
import os
import sys
from typing import Optional

import gymnasium as gym
import numpy as np
from PIL import Image
from mcp.server.fastmcp import FastMCP

# Global state for the BrowserGym environment
_env: Optional[gym.Env] = None
_last_obs: Optional[dict] = None
_dataset_name: str = ""
_task_name: str = ""


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
        # Core only - openended task
        import browsergym.core


def _screenshot_to_base64(screenshot: np.ndarray) -> str:
    """Convert numpy screenshot array to base64 PNG string."""
    img = Image.fromarray(screenshot)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _get_axtree_text(obs: dict) -> str:
    """Extract accessibility tree as text from observation."""
    if "axtree_txt" in obs:
        return obs["axtree_txt"]
    if "axtree_object" in obs and obs["axtree_object"]:
        # Convert axtree object to string representation
        return str(obs["axtree_object"])
    return ""


def _execute_action(action: str) -> dict:
    """Execute an action and return result with screenshot."""
    global _env, _last_obs

    if _env is None:
        return {"error": "Environment not initialized. Call reset_env() first."}

    try:
        obs, reward, terminated, truncated, info = _env.step(action)
        _last_obs = obs

        result = {
            "reward": float(reward),
            "terminated": terminated,
            "truncated": truncated,
            "done": terminated or truncated,
        }

        # Include screenshot
        if "screenshot" in obs and obs["screenshot"] is not None:
            result["screenshot"] = _screenshot_to_base64(obs["screenshot"])

        # Include error if any
        if "last_action_error" in obs and obs["last_action_error"]:
            result["action_error"] = obs["last_action_error"]

        return result
    except Exception as e:
        return {"error": str(e)}


# Create MCP server
mcp = FastMCP("browsergym", json_response=True)


# ========== Environment Lifecycle ==========

@mcp.tool()
def reset_env() -> dict:
    """Reset the BrowserGym environment and return initial observation.

    Returns:
        dict with keys: goal, screenshot (base64), axtree
    """
    global _env, _last_obs, _dataset_name, _task_name

    try:
        # Import the benchmark module
        _import_benchmark(_dataset_name)

        # Build task ID
        if _dataset_name == "openended" or not _task_name:
            task_id = "browsergym/openended"
        else:
            task_id = f"browsergym/{_dataset_name}.{_task_name}"

        # Close existing env if any
        if _env is not None:
            try:
                _env.close()
            except:
                pass

        # Create new environment
        _env = gym.make(task_id, headless=False)
        obs, info = _env.reset()
        _last_obs = obs

        result = {
            "task_id": task_id,
            "goal": obs.get("goal", "") or str(obs.get("goal_object", "")),
        }

        if "screenshot" in obs and obs["screenshot"] is not None:
            result["screenshot"] = _screenshot_to_base64(obs["screenshot"])

        result["axtree"] = _get_axtree_text(obs)

        return result
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def close_env() -> dict:
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
        return {"error": str(e)}


# ========== Task Management ==========

@mcp.tool()
def list_tasks(benchmark: str) -> dict:
    """List all available tasks for a benchmark.

    Args:
        benchmark: One of 'miniwob', 'webarena', 'visualwebarena', 'workarena', 'assistantbench'

    Returns:
        dict with 'tasks' list
    """
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
        return {"error": str(e)}


@mcp.tool()
def get_goal() -> dict:
    """Get the current task goal/instruction."""
    global _last_obs

    if _last_obs is None:
        return {"error": "No observation available. Call reset_env() first."}

    goal = _last_obs.get("goal", "") or str(_last_obs.get("goal_object", ""))
    return {"goal": goal}


@mcp.tool()
def check_task_status() -> dict:
    """Check if the current task is completed.

    Returns:
        dict with keys: reward, done, info
    """
    global _env, _last_obs

    if _env is None or _last_obs is None:
        return {"error": "Environment not initialized. Call reset_env() first."}

    # The last step result contains termination info
    # We need to check via a noop action or access env internals
    try:
        # Execute noop to get current status
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
        return {"error": str(e)}


# ========== Generic Action Execution ==========

@mcp.tool()
def step(action: str) -> dict:
    """Execute a BrowserGym action string.

    Args:
        action: Action string like "click('a123')", "fill('a456', 'text')", etc.

    Returns:
        dict with keys: reward, done, screenshot
    """
    return _execute_action(action)


# ========== BID Element Interaction ==========

@mcp.tool()
def click(bid: str, button: str = "left") -> dict:
    """Click an element by its browser ID (bid).

    Args:
        bid: Browser element ID (e.g., 'a123')
        button: Mouse button - 'left', 'middle', or 'right'
    """
    return _execute_action(f"click('{bid}', button='{button}')")


@mcp.tool()
def dblclick(bid: str, button: str = "left") -> dict:
    """Double-click an element by its browser ID.

    Args:
        bid: Browser element ID
        button: Mouse button - 'left', 'middle', or 'right'
    """
    return _execute_action(f"dblclick('{bid}', button='{button}')")


@mcp.tool()
def hover(bid: str) -> dict:
    """Hover over an element by its browser ID.

    Args:
        bid: Browser element ID
    """
    return _execute_action(f"hover('{bid}')")


@mcp.tool()
def fill(bid: str, value: str) -> dict:
    """Fill an input field with text.

    Args:
        bid: Browser element ID of the input
        value: Text to fill
    """
    # Escape quotes in value
    escaped_value = value.replace("'", "\\'")
    return _execute_action(f"fill('{bid}', '{escaped_value}')")


@mcp.tool()
def press(bid: str, key: str) -> dict:
    """Press a key combination on an element.

    Args:
        bid: Browser element ID
        key: Key combination like 'Enter', 'Tab', 'ControlOrMeta+a'
    """
    return _execute_action(f"press('{bid}', '{key}')")


@mcp.tool()
def focus(bid: str) -> dict:
    """Focus on an element by its browser ID.

    Args:
        bid: Browser element ID
    """
    return _execute_action(f"focus('{bid}')")


@mcp.tool()
def clear(bid: str) -> dict:
    """Clear an input field.

    Args:
        bid: Browser element ID of the input
    """
    return _execute_action(f"clear('{bid}')")


@mcp.tool()
def select_option(bid: str, options: str) -> dict:
    """Select option(s) in a dropdown.

    Args:
        bid: Browser element ID of the select element
        options: Option value(s) to select
    """
    return _execute_action(f"select_option('{bid}', '{options}')")


@mcp.tool()
def drag_and_drop(from_bid: str, to_bid: str) -> dict:
    """Drag an element and drop it on another element.

    Args:
        from_bid: Browser element ID to drag from
        to_bid: Browser element ID to drop on
    """
    return _execute_action(f"drag_and_drop('{from_bid}', '{to_bid}')")


# ========== Coordinate-based Actions ==========

@mcp.tool()
def mouse_move(x: float, y: float) -> dict:
    """Move mouse to coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
    """
    return _execute_action(f"mouse_move({x}, {y})")


@mcp.tool()
def mouse_click(x: float, y: float, button: str = "left") -> dict:
    """Click at coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
        button: Mouse button - 'left', 'middle', or 'right'
    """
    return _execute_action(f"mouse_click({x}, {y}, button='{button}')")


@mcp.tool()
def mouse_dblclick(x: float, y: float, button: str = "left") -> dict:
    """Double-click at coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
        button: Mouse button
    """
    return _execute_action(f"mouse_dblclick({x}, {y}, button='{button}')")


@mcp.tool()
def mouse_down(x: float, y: float, button: str = "left") -> dict:
    """Press mouse button at coordinates (without releasing).

    Args:
        x: X coordinate
        y: Y coordinate
        button: Mouse button
    """
    return _execute_action(f"mouse_down({x}, {y}, button='{button}')")


@mcp.tool()
def mouse_up(x: float, y: float, button: str = "left") -> dict:
    """Release mouse button at coordinates.

    Args:
        x: X coordinate
        y: Y coordinate
        button: Mouse button
    """
    return _execute_action(f"mouse_up({x}, {y}, button='{button}')")


@mcp.tool()
def mouse_drag_and_drop(from_x: float, from_y: float, to_x: float, to_y: float) -> dict:
    """Drag from one coordinate to another.

    Args:
        from_x: Starting X coordinate
        from_y: Starting Y coordinate
        to_x: Ending X coordinate
        to_y: Ending Y coordinate
    """
    return _execute_action(f"mouse_drag_and_drop({from_x}, {from_y}, {to_x}, {to_y})")


@mcp.tool()
def scroll(delta_x: float = 0, delta_y: float = 100) -> dict:
    """Scroll the page.

    Args:
        delta_x: Horizontal scroll amount (positive = right)
        delta_y: Vertical scroll amount (positive = down)
    """
    return _execute_action(f"scroll({delta_x}, {delta_y})")


# ========== Keyboard Actions ==========

@mcp.tool()
def keyboard_press(key: str) -> dict:
    """Press a key.

    Args:
        key: Key to press (e.g., 'Enter', 'Tab', 'Escape')
    """
    return _execute_action(f"keyboard_press('{key}')")


@mcp.tool()
def keyboard_type(text: str) -> dict:
    """Type text using keyboard.

    Args:
        text: Text to type
    """
    escaped_text = text.replace("'", "\\'")
    return _execute_action(f"keyboard_type('{escaped_text}')")


@mcp.tool()
def keyboard_down(key: str) -> dict:
    """Press and hold a key.

    Args:
        key: Key to hold
    """
    return _execute_action(f"keyboard_down('{key}')")


@mcp.tool()
def keyboard_up(key: str) -> dict:
    """Release a held key.

    Args:
        key: Key to release
    """
    return _execute_action(f"keyboard_up('{key}')")


# ========== Navigation ==========

@mcp.tool()
def goto(url: str) -> dict:
    """Navigate to a URL.

    Args:
        url: URL to navigate to
    """
    return _execute_action(f"goto('{url}')")


@mcp.tool()
def go_back() -> dict:
    """Navigate back in browser history."""
    return _execute_action("go_back()")


@mcp.tool()
def go_forward() -> dict:
    """Navigate forward in browser history."""
    return _execute_action("go_forward()")


# ========== Tab Management ==========

@mcp.tool()
def new_tab() -> dict:
    """Open a new browser tab."""
    return _execute_action("new_tab()")


@mcp.tool()
def tab_close() -> dict:
    """Close the current tab."""
    return _execute_action("tab_close()")


@mcp.tool()
def tab_focus(index: int) -> dict:
    """Focus on a specific tab by index.

    Args:
        index: Tab index (0-based)
    """
    return _execute_action(f"tab_focus({index})")


# ========== Observation ==========

@mcp.tool()
def get_screenshot() -> dict:
    """Get the current page screenshot as base64 PNG."""
    global _last_obs

    if _last_obs is None:
        return {"error": "No observation available. Call reset_env() first."}

    if "screenshot" in _last_obs and _last_obs["screenshot"] is not None:
        return {"screenshot": _screenshot_to_base64(_last_obs["screenshot"])}

    return {"error": "Screenshot not available"}


@mcp.tool()
def get_axtree() -> dict:
    """Get the accessibility tree of the current page.

    The accessibility tree contains all interactive elements with their browser IDs (bid).
    """
    global _last_obs

    if _last_obs is None:
        return {"error": "No observation available. Call reset_env() first."}

    return {"axtree": _get_axtree_text(_last_obs)}


@mcp.tool()
def get_page_state() -> dict:
    """Get current page state including URL, title, and open tabs."""
    global _last_obs

    if _last_obs is None:
        return {"error": "No observation available. Call reset_env() first."}

    return {
        "url": _last_obs.get("url", ""),
        "open_pages_urls": _last_obs.get("open_pages_urls", []),
        "open_pages_titles": _last_obs.get("open_pages_titles", []),
        "active_page_index": _last_obs.get("active_page_index", 0),
    }


# ========== Other ==========

@mcp.tool()
def noop(wait_ms: float = 1000) -> dict:
    """Do nothing and wait.

    Args:
        wait_ms: Milliseconds to wait
    """
    return _execute_action(f"noop(wait_ms={wait_ms})")


def main():
    global _dataset_name, _task_name

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="BrowserGym MCP Server")
    parser.add_argument("--dataset", "-d",
                        default=os.environ.get("DATASET_NAME", "openended"),
                        help="Dataset/benchmark name (miniwob, webarena, etc.)")
    parser.add_argument("--task", "-t",
                        default=os.environ.get("TASK_NAME", ""),
                        help="Task name within the dataset")

    args = parser.parse_args()

    _dataset_name = args.dataset
    _task_name = args.task

    # Log to stderr (not stdout, which is used for MCP protocol)
    print(f"Starting BrowserGym MCP Server", file=sys.stderr)
    print(f"  Dataset: {_dataset_name}", file=sys.stderr)
    print(f"  Task: {_task_name or '(none)'}", file=sys.stderr)

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
