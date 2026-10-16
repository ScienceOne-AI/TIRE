"""Generate and execute tests for the formula program, as a method step."""

import ast
import prompts
from client import json_response
from sandbox import evaluate


def run(item, client):
    values = prompts.formula_values(item["formula"], quoted=True)
    values["python_code"] = item["program"]["code"]
    prompt = prompts.render(prompts.UNIT_TESTS, values)
    tests = client.complete(item["id"], "unit_tests", prompt, parse=json_response)["parsed"]["test_cases"]
    ast.parse(tests)
    item["program"]["tests"] = tests
    result = evaluate({"mode": "unit", **item["program"]})
    item["unit_test_result"] = result
    if result.get("status") != "passed":
        raise ValueError("Generated program failed its unit tests: " + str(result))
    return item
