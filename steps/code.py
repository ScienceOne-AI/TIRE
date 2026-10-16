"""Generate one executable formula program using the Appendix C.1 prompt."""

import ast
import prompts
from client import json_response


def run(item, client):
    prompt = prompts.render(prompts.CODE, prompts.formula_values(item["formula"], escaped=True))
    result = client.complete(item["id"], "code", prompt, parse=json_response)["parsed"]
    code = result["python_code"]
    names = [n.name for n in ast.parse(code).body if isinstance(n, ast.FunctionDef)]
    if len(names) != 1:
        raise ValueError("Expected one top-level formula function")
    item["program"] = {"code": code, "function": names[0]}
    return item
