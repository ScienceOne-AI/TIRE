"""Small JSON helpers shared by the generation steps."""

import hashlib
import json
import os
from pathlib import Path



def digest(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def read_jsonl(path):
    rows = []
    with Path(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Line {number} must be an object")
                rows.append(value)
    return rows


def write_json(path, value, *, lines=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ("".join(json.dumps(x, ensure_ascii=False, allow_nan=False) + "\n" for x in value)
            if lines else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)

