#!/usr/bin/env python3
"""Generate BrowseComp task and criteria files for LiteEvolve evolution.

BrowseComp is a web browsing benchmark from OpenAI's simple-evals.
Dataset contains encrypted problems and answers that are decrypted at generation time.

Usage:
    python generate_browsecomp.py                    # Generate all tasks
    python generate_browsecomp.py --limit 10         # Generate first 10 tasks
"""

import argparse
import base64
import hashlib
from pathlib import Path

import pandas as pd


DATASET_URL = "https://openaipublic.blob.core.windows.net/simple-evals/browse_comp_test_set.csv"


def decrypt(ciphertext: str, password: str) -> str:
    """Decrypt XOR-encrypted text using SHA256-derived key.

    This matches OpenAI's decryption in browsecomp_eval.py.

    Args:
        ciphertext: Base64-encoded encrypted text
        password: Decryption password (canary field)

    Returns:
        Decrypted plaintext string
    """
    if not ciphertext or not password:
        return ""

    # Derive key from password using SHA256
    key = hashlib.sha256(password.encode()).digest()

    # Decode base64 ciphertext
    try:
        encrypted_bytes = base64.b64decode(ciphertext)
    except Exception:
        return ciphertext  # Return as-is if not valid base64

    # XOR decrypt
    decrypted_bytes = bytes(
        encrypted_bytes[i] ^ key[i % len(key)]
        for i in range(len(encrypted_bytes))
    )

    return decrypted_bytes.decode("utf-8", errors="replace")


def download_dataset() -> pd.DataFrame:
    """Download BrowseComp dataset from OpenAI.

    Returns:
        DataFrame with columns: problem, answer, canary
    """
    print(f"Downloading dataset from {DATASET_URL}...")
    df = pd.read_csv(DATASET_URL)
    print(f"Downloaded {len(df)} examples")
    return df


def generate_task_files(output_dir: Path, examples: list[dict]) -> None:
    """Generate task files with decrypted problems."""
    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    for i, example in enumerate(examples, 1):
        problem = decrypt(example.get("problem", ""), example.get("canary", ""))
        task_file = tasks_dir / f"{i:03d}.txt"
        task_file.write_text(problem.strip() + "\n")

    print(f"Generated {len(examples)} task files in {tasks_dir}")


def generate_criteria_files(output_dir: Path, examples: list[dict]) -> None:
    """Generate criteria files with decrypted answers."""
    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)

    for i, example in enumerate(examples, 1):
        answer = decrypt(example.get("answer", ""), example.get("canary", ""))
        criteria_file = criteria_dir / f"{i:03d}.txt"
        criteria_file.write_text(answer.strip() + "\n")

    print(f"Generated {len(examples)} criteria files in {criteria_dir}")


def generate_task_template(output_dir: Path) -> None:
    """Generate the task template.jinja2."""
    template = '''You are a web browsing agent. Answer the following question by browsing the web.

## Question

{{ content.strip() }}

## Instructions

1. Use your web browsing capabilities to search for and gather information
2. Navigate to relevant websites, read content, and follow links as needed
3. Think step-by-step about what information you need
4. Provide a clear, concise answer based on what you find

## Your Answer

Explain your research process, then provide the final answer.
'''

    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    template_file = tasks_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated task template at {template_file}")


def generate_criteria_template(output_dir: Path) -> None:
    """Generate the criteria template.jinja2."""
    template = '''## Evaluation Criterion

**Ground Truth Answer:** {{ content.strip() }}

**Success Criteria:**
- The agent's answer matches or is semantically equivalent to the ground truth
- Numerical equivalence is acceptable (e.g., "1,000" = "1000")
- Minor formatting differences are acceptable if meaning is preserved

**Failure Criteria:**
- Agent provided incorrect information
- Agent failed to find an answer
- Agent's answer contradicts the ground truth
'''

    criteria_dir = output_dir / "criteria"
    criteria_dir.mkdir(parents=True, exist_ok=True)
    template_file = criteria_dir / "template.jinja2"
    template_file.write_text(template)
    print(f"Generated criteria template at {template_file}")


def generate_playbook_schema(output_dir: Path) -> None:
    """Generate a BrowseComp-specific playbook schema."""
    schema = '''{
  "playbook_version": 0,
  "title": "BrowseComp Web Browsing Strategy",
  "description": "Guidance for answering questions that require web browsing",
  "sections": {
    "workflow": [
      "1. Read the question carefully to understand what information is needed",
      "2. Identify key terms and entities to search for",
      "3. Start with a web search using relevant keywords",
      "4. Navigate to authoritative sources (official sites, Wikipedia, etc.)",
      "5. Extract relevant facts and verify across sources if needed",
      "6. Formulate a clear, concise answer"
    ],
    "search_strategies": [
      "Use specific keywords from the question",
      "Include entity names, dates, or numbers when relevant",
      "Try alternative phrasings if initial search fails",
      "Look for official sources first (company sites, government, etc.)"
    ],
    "information_extraction": [
      "Focus on factual information that directly answers the question",
      "Note specific numbers, dates, names as they appear",
      "Cross-reference if information seems uncertain",
      "Prefer recent sources for time-sensitive information"
    ],
    "answer_formulation": [
      "Answer the question directly and concisely",
      "Include only information that was requested",
      "Use the same format as the question implies (number, name, list, etc.)",
      "Double-check the answer against the original question"
    ]
  },
  "logs": []
}'''

    schema_file = output_dir / "PLAYBOOK_SCHEMA.txt"
    schema_file.write_text(schema)
    print(f"Generated playbook schema at {schema_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate BrowseComp task files for LiteEvolve")
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path(__file__).parent,
        help="Output directory (default: same as script location)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tasks to generate"
    )

    args = parser.parse_args()

    # Download dataset
    df = download_dataset()
    examples = [row.to_dict() for _, row in df.iterrows()]

    if args.limit:
        examples = examples[:args.limit]

    print(f"Generating files for {len(examples)} BrowseComp tasks...")

    # Generate all files
    generate_task_files(args.output_dir, examples)
    generate_criteria_files(args.output_dir, examples)
    generate_task_template(args.output_dir)
    generate_criteria_template(args.output_dir)
    generate_playbook_schema(args.output_dir)

    print(f"\nDone! Run evolution with:")
    print(f"  uv run evolve --provider claude \\")
    print(f"    --task-dir {args.output_dir}/tasks \\")
    print(f"    --criterion-dir {args.output_dir}/criteria \\")
    print(f"    --schema-playbook {args.output_dir}/PLAYBOOK_SCHEMA.txt")


if __name__ == "__main__":
    main()
