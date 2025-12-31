# ARC-AGI-2 Tasks for LiteEvolve

This directory contains ARC-AGI-2 (Abstraction and Reasoning Corpus) tasks for use with LiteEvolve's playbook evolution system.

## About ARC-AGI-2

ARC-AGI-2 is a benchmark for measuring AI systems' ability to perform abstract reasoning and pattern recognition. Each task presents:
- 2-5 training examples showing input→output grid transformations
- 1-2 test inputs where the model must predict the output

Grids are 2D arrays of integers 0-9 representing colors, with dimensions from 1×1 to 30×30.

**Difficulty**: Pure LLMs score ~0% on ARC-AGI-2. Even OpenAI's o3 achieves only ~4%.

## Setup

### Option 1: Simple Subset (Recommended for starting)

Generate 200 simpler tasks (sorted by input grid size):

```bash
cd examples/arc-agi-2
python generate_arc_tasks.py      # First, download the dataset
python generate_simple_subset.py  # Then, create simple subset
```

This generates ~215 tasks with the smallest input grids (12-236 total cells vs full range of 12-4500).

### Option 2: Full Dataset

Generate all ~1100 task/criterion pairs:

```bash
cd examples/arc-agi-2
python generate_arc_tasks.py
```

This will:
- Clone the ARC-AGI-2 repository to `data/ARC-AGI-2/`
- Generate all training + evaluation tasks

## Usage

Run playbook evolution on ARC tasks:

```bash
uv run evolve \
  --provider claude \
  --task-dir examples/arc-agi-2/tasks \
  --criterion-dir examples/arc-agi-2/criteria \
  --step-size 100 \
  --batch-size 10
```

## Task Format

**Task files** (`tasks/*.txt`): JSON containing training examples and test input
```json
{
  "train": [
    {"input": [[0,1],[1,0]], "output": [[1,0],[0,1]]}
  ],
  "test": {"input": [[0,2],[2,0]]}
}
```

**Criterion files** (`criteria/*.txt`): Expected output grid
```json
[[2,0],[0,2]]
```

## Expected Results

- Initial accuracy will be very low (~0%)
- The playbook should evolve strategies for pattern recognition
- Common patterns: object detection, symmetry, counting, color mapping, spatial transformations

## References

- [ARC-AGI-2 Repository](https://github.com/arcprize/ARC-AGI-2)
- [ARC Prize](https://arcprize.org/)
- [On the Measure of Intelligence (Chollet, 2019)](https://arxiv.org/abs/1911.01547)
