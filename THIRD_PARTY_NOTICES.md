# Third-party Sources and Dependencies

## Project sources

| Source | Published license | Upstream |
| --- | --- | --- |
| PHYSICS | MIT; Copyright (c) 2025 Yale-NLP | https://github.com/yale-nlp/Physics/blob/main/LICENSE |
| SciBench | MIT; Copyright (c) 2023 Xiaoxuan Wang | https://github.com/mandyyyyii/scibench/blob/main/LICENSE |
| Qwen3-235B-A22B-Thinking-2507 | Apache-2.0 | https://huggingface.co/Qwen/Qwen3-235B-A22B-Thinking-2507/blob/main/LICENSE |

The code repository does not bundle the source benchmark archives, model
weights or historical training answers. Upstream software licenses do not
guarantee rights to redistribute underlying textbook, examination or provider
content. Source identifiers are retained for attribution and traceability in
the local release records.

## Runtime dependencies

Installed dependencies are not vendored. Their distributions retain their own
notices and licenses:

- HTTPX: BSD-3-Clause
- NumPy: BSD-3-Clause
- SciPy: BSD-3-Clause
- SymPy: BSD-3-Clause
- Math-Verify: Apache-2.0
- bubblewrap: LGPL-2.1-or-later

Model-service contracts are separate from software licenses. Users must check
the terms of the provider and endpoint they choose before sending data or
redistributing generated outputs.
