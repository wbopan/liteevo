#!/usr/bin/env python3
"""Generate 5x5 maze walking puzzle tasks."""

import os
import random
from collections import deque
from typing import List, Tuple, Optional


def generate_maze(size: int = 5) -> List[List[str]]:
    """Generate a random 5x5 maze with walls.

    Returns a grid where:
    - '#' is a wall
    - ' ' is a path
    - 'S' is start
    - 'E' is end
    """
    # Start with all open paths
    maze = [[' ' for _ in range(size)] for _ in range(size)]

    # Add random walls (about 40% of cells)
    num_walls = int(size * size * 0.4)
    positions = [(i, j) for i in range(size) for j in range(size)
                 if (i, j) != (0, 0) and (i, j) != (size - 1, size - 1)]

    random.shuffle(positions)
    for i in range(min(num_walls, len(positions))):
        x, y = positions[i]
        maze[x][y] = '#'

    # Place start and end
    maze[0][0] = 'S'
    maze[size - 1][size - 1] = 'E'

    # Ensure path exists
    path = find_path(maze)
    if not path:
        maze = ensure_path_exists(maze, size)

    return maze


def ensure_path_exists(maze: List[List[str]], size: int) -> List[List[str]]:
    """Ensure a path exists from S to E by removing walls along a route."""
    # Try to find a path by removing walls one by one
    for _ in range(size * 2):
        path = find_path(maze)
        if path:
            return maze

        # Find a blocked cell and clear it
        # Use BFS from start to find closest wall to clear
        queue = deque([(0, 0)])
        visited = {(0, 0)}
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

        while queue:
            x, y = queue.popleft()
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if 0 <= nx < size and 0 <= ny < size and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    if maze[nx][ny] == '#':
                        maze[nx][ny] = ' '
                        break
                    queue.append((nx, ny))
            else:
                continue
            break

    # Fallback: clear a direct path
    for i in range(size):
        if maze[i][i] == '#':
            maze[i][i] = ' '

    maze[0][0] = 'S'
    maze[size - 1][size - 1] = 'E'
    return maze


def find_path(maze: List[List[str]]) -> Optional[List[Tuple[int, int]]]:
    """Find shortest path from S to E using BFS. Returns list of (row, col) positions."""
    size = len(maze)

    # Find start position
    start = None
    end = None
    for i in range(size):
        for j in range(size):
            if maze[i][j] == 'S':
                start = (i, j)
            elif maze[i][j] == 'E':
                end = (i, j)

    if not start or not end:
        return None

    # BFS
    queue = deque([(start, [start])])
    visited = {start}
    directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]

    while queue:
        (x, y), path = queue.popleft()

        if (x, y) == end:
            return path

        for dx, dy in directions:
            nx, ny = x + dx, y + dy
            if (0 <= nx < size and 0 <= ny < size and
                    (nx, ny) not in visited and maze[nx][ny] != '#'):
                visited.add((nx, ny))
                queue.append(((nx, ny), path + [(nx, ny)]))

    return None


def path_to_directions(path: List[Tuple[int, int]]) -> str:
    """Convert path coordinates to direction string (U/D/L/R)."""
    if not path or len(path) < 2:
        return ""

    directions = []
    for i in range(1, len(path)):
        prev_row, prev_col = path[i - 1]
        curr_row, curr_col = path[i]

        if curr_row < prev_row:
            directions.append('U')  # Up
        elif curr_row > prev_row:
            directions.append('D')  # Down
        elif curr_col < prev_col:
            directions.append('L')  # Left
        elif curr_col > prev_col:
            directions.append('R')  # Right

    return ''.join(directions)


def maze_to_string(maze: List[List[str]]) -> str:
    """Convert maze grid to string representation."""
    return '\n'.join(''.join(row) for row in maze)


def generate_tasks(output_dir: str, num_tasks: int = 30, size: int = 5):
    """Generate maze walking puzzle tasks."""
    tasks_dir = os.path.join(output_dir, "tasks")
    criteria_dir = os.path.join(output_dir, "criteria")

    os.makedirs(tasks_dir, exist_ok=True)
    os.makedirs(criteria_dir, exist_ok=True)

    generated = 0
    attempts = 0
    max_attempts = num_tasks * 20
    seen_paths = set()

    while generated < num_tasks and attempts < max_attempts:
        attempts += 1

        maze = generate_maze(size)
        path = find_path(maze)

        if not path or len(path) < 4:
            continue  # Skip trivial mazes

        directions = path_to_directions(path)

        # Skip if we've seen this exact path before
        if directions in seen_paths:
            continue
        seen_paths.add(directions)

        generated += 1
        idx = generated

        task_file = os.path.join(tasks_dir, f"{idx:03d}.txt")
        criterion_file = os.path.join(criteria_dir, f"{idx:03d}.txt")

        maze_str = maze_to_string(maze)

        task_content = f"""Navigate through this 5x5 maze from S (start) to E (end).
Give the path as a sequence of directions: U (up), D (down), L (left), R (right).

Legend:
- S = Start position
- E = End position
- # = Wall (cannot pass)
- (space) = Open path

Maze:
{maze_str}

What is the shortest path from S to E?
"""

        criterion_content = f"the path should be {directions} (length: {len(directions)} steps)\n"

        with open(task_file, "w") as f:
            f.write(task_content)

        with open(criterion_file, "w") as f:
            f.write(criterion_content)

        print(f"Generated task {idx:03d}: path length {len(directions)} ({directions})")


if __name__ == "__main__":
    import sys

    output_dir = sys.argv[1] if len(sys.argv) > 1 else "data/"
    generate_tasks(output_dir)
    print(f"\nGenerated 30 maze tasks in {output_dir}/tasks/ and {output_dir}/criteria/")
