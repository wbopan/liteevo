#!/usr/bin/env python3
"""Generate ASCII art number recognition tasks."""

import os
import random

# ASCII art templates for digits 0-9 (7 lines each, 5 chars wide)
DIGITS = {
    '0': [
        " ███ ",
        "█   █",
        "█   █",
        "█   █",
        "█   █",
        "█   █",
        " ███ ",
    ],
    '1': [
        "  █  ",
        " ██  ",
        "  █  ",
        "  █  ",
        "  █  ",
        "  █  ",
        " ███ ",
    ],
    '2': [
        " ███ ",
        "█   █",
        "    █",
        "  ██ ",
        " █   ",
        "█    ",
        "█████",
    ],
    '3': [
        "█████",
        "    █",
        "   █ ",
        "  ██ ",
        "    █",
        "█   █",
        " ███ ",
    ],
    '4': [
        "   █ ",
        "  ██ ",
        " █ █ ",
        "█  █ ",
        "█████",
        "   █ ",
        "   █ ",
    ],
    '5': [
        "█████",
        "█    ",
        "████ ",
        "    █",
        "    █",
        "█   █",
        " ███ ",
    ],
    '6': [
        " ███ ",
        "█   █",
        "█    ",
        "████ ",
        "█   █",
        "█   █",
        " ███ ",
    ],
    '7': [
        "█████",
        "    █",
        "   █ ",
        "  █  ",
        " █   ",
        " █   ",
        " █   ",
    ],
    '8': [
        " ███ ",
        "█   █",
        "█   █",
        " ███ ",
        "█   █",
        "█   █",
        " ███ ",
    ],
    '9': [
        " ███ ",
        "█   █",
        "█   █",
        " ████",
        "    █",
        "█   █",
        " ███ ",
    ],
}


def number_to_ascii(number: int) -> str:
    """Convert a number to ASCII art."""
    digits = str(number)
    lines = [""] * 7

    for i, d in enumerate(digits):
        digit_art = DIGITS[d]
        for line_idx in range(7):
            if i > 0:
                lines[line_idx] += "  "  # spacing between digits
            lines[line_idx] += digit_art[line_idx]

    return "\n".join(lines)


def generate_tasks(output_dir: str, num_tasks: int = 30):
    """Generate ASCII art number recognition tasks."""
    tasks_dir = os.path.join(output_dir, "tasks")
    criteria_dir = os.path.join(output_dir, "criteria")

    os.makedirs(tasks_dir, exist_ok=True)
    os.makedirs(criteria_dir, exist_ok=True)

    # Generate random numbers (3 digits for variety)
    numbers = random.sample(range(100, 1000), num_tasks)

    for idx, number in enumerate(numbers, start=1):
        task_file = os.path.join(tasks_dir, f"{idx:03d}.txt")
        criterion_file = os.path.join(criteria_dir, f"{idx:03d}.txt")

        ascii_art = number_to_ascii(number)

        task_content = f"""Please recognize what number is in the following ascii art:

{ascii_art}
"""

        criterion_content = f"the number should be {number}\n"

        with open(task_file, "w") as f:
            f.write(task_content)

        with open(criterion_file, "w") as f:
            f.write(criterion_content)

        print(f"Generated task {idx:03d}: {number}")


if __name__ == "__main__":
    import sys

    output_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    generate_tasks(output_dir)
    print(f"\nGenerated 30 tasks in {output_dir}/tasks/ and {output_dir}/criteria/")
