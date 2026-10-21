<div align="center">

# TIRE

**Top-Down Formula Instantiation with Reliable Execution**

[![GitHub](https://img.shields.io/badge/GitHub-TIRE-181717?logo=github)](https://github.com/ScienceOne-AI/TIRE)
[![Hugging Face](https://img.shields.io/badge/Hugging%20Face-TIRE-yellow)](https://huggingface.co/datasets/ScienceOne-AI/TIRE)
[![arXiv](https://img.shields.io/badge/arXiv-2610.25134-b31b1b?logo=arxiv)](https://arxiv.org/abs/2610.25134)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**English** | [简体中文](README_zh.md)

</div>

## Project Introduction

TIRE is a lightweight pipeline for constructing physics reasoning data from
reusable formulas. It turns formulas into executable programs, generates and
runs unit tests, instantiates numerical parameters, creates English questions
and teacher solutions, and filters the results against independently executed
reference answers. The repository presents a small and inspectable data
construction workflow.

## Highlights

- **Formula-guided generation**: use an existing formula or extract one from a
  source problem.
- **Execution-based verification**: run generated programs and tests in a
  `bubblewrap` sandbox.
- **Answer-verified distillation**: the teacher does not receive the reference
  answer; incorrect, truncated and malformed responses are filtered.
- **Simple interfaces**: stages exchange ordinary Python dictionaries and can
  be inspected or replaced independently.

## Pipeline

| Stage | Function |
| --- | --- |
| Formula | Extract and filter a reusable physical relation |
| Program | Generate a Python calculation function |
| Unit test | Generate and run physically reasonable test cases |
| Parameters | Instantiate values and optional seeded perturbations |
| Reference | Execute the function to obtain the numerical target |
| Question | Generate and normalize the English problem statement |
| Distillation | Ask the teacher model to solve the problem |
| Verification | Extract the final `\\boxed{}` answer and compare it with the target |
| Export | Write accepted JSONL, SFT and GRPO records |

## Dataset Release

The associated `TIRE-PHYSICS-2000` dataset is released separately from the code:

| Platform | Link | Contents |
| --- | --- | --- |
| Hugging Face | [ScienceOne-AI/TIRE](https://huggingface.co/datasets/ScienceOne-AI/TIRE) | 2,000 English physics QA records |

Each record contains `question` and `answer` fields. It is a curated release
subset, not the full TIRE-19k training set or an evaluation split.

The dataset is released under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
It can be loaded with:

```python
from datasets import load_dataset

dataset = load_dataset("ScienceOne-AI/TIRE", split="train")
```

## Installation

Python 3.10+, Linux and `bubblewrap` with working user namespaces are required.

```bash
python -m pip install -r requirements.txt
export TIRE_BASE_URL="https://your-endpoint/v1"
export TIRE_API_KEY="YOUR_API_KEY"
```

The model ID is read from `config.example.json`; use an ID supported by the
endpoint. The current client sends a streaming OpenAI-compatible Chat
Completions request with `enable_thinking: true` and expects the returned model
identifier to match the configured ID. An unauthenticated local endpoint must
use the literal `TIRE_API_KEY=EMPTY`; the current client sends
`Authorization: Bearer EMPTY`.

## Quick Start

The included example directly supplies a capacitance formula, so formula
extraction is skipped:

```bash
python pipeline.py \
  --config config.example.json \
  --input examples/formulas.jsonl \
  --output outputs \
  --limit 1
```

The output directory contains accepted samples, SFT/GRPO exports, rejected
records and API cache files. The verifier extracts the last complete
`\\boxed{}` expression and checks the final numerical answer against the
executed reference with a 5% relative tolerance.

## Code Structure

```text
pipeline.py              Pipeline entry point
prompts.py               Prompts aligned with Appendix C.1
client.py                API client, retries and cache
sandbox.py               Isolated program execution
steps/                   Formula, program, unit-test, parameter, question,
                         distillation, verification and export stages
```

## License

The code is released under the [Apache License 2.0](LICENSE). The dataset is
released under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/).
See `THIRD_PARTY_NOTICES.md` for upstream sources and runtime dependencies.

## 📖 Citation

If TIRE is useful for your research, please cite our paper.

```bibtex
@misc{tire2026,
  title  = {TIRE: Top-Down Formula Instantiation with Reliable Execution for Physics Problem Synthesis},
  author = {Xiaoyu Wu and Zhaoxin Yu and Xinglin Xiao and Nan Xu},
  year   = {2026},
  url    = {https://arxiv.org/abs/2610.25134}
}
```
