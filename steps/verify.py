"""Schema, executable-reference and final-answer verification without API calls."""

import re
from steps import digest
from sandbox import evaluate

PROTOCOL = "final-last-box-reference-relative-5pct-v1"
LENGTH_REASONS = {"length", "max_tokens", "max_output_tokens", "token_limit"}


from steps.format_answers import split_response, last_boxed


def record_hash(row):
    return digest({k: v for k, v in row.items() if k != "verification"})


def validate(row):
    if row.get("schema_version") != 1:
        raise ValueError("Unsupported sample schema")
    for key in ("id", "question"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError("Missing " + key)
    for key in ("formula", "program", "parameters", "reference", "teacher", "provenance", "rights"):
        if not isinstance(row.get(key), dict):
            raise ValueError("Missing object: " + key)
    for key in ("id", "name", "expression"):
        if not row["formula"].get(key):
            raise ValueError("Missing formula " + key)
    if not all(isinstance(row["program"].get(k), str) and row["program"][k].strip()
               for k in ("code", "tests", "function")):
        raise ValueError("Program, tests and function are required")
    if "value" not in row["reference"] or "unit" not in row["reference"]:
        raise ValueError("Reference value and explicit unit metadata are required")
    messages = row.get("messages")
    if not isinstance(messages, list) or [m.get("role") for m in messages] not in (
            ["user", "assistant"], ["system", "user", "assistant"]):
        raise ValueError("Expected one user/assistant pair and optional system message")
    if any(not isinstance(m.get("content"), str) or not m["content"].strip() for m in messages):
        raise ValueError("Empty message")
    if messages[-2]["content"] != row["question"]:
        raise ValueError("Question differs from the training prompt")
    if not row["teacher"].get("model"):
        raise ValueError("Missing actual teacher model identifier")
    if row["rights"].get("status") not in ("pending", "approved"):
        raise ValueError("Unknown rights status")
    if row["rights"]["status"] == "approved" and not row["rights"].get("evidence"):
        raise ValueError("Approved records require explicit rights evidence")
    digest(row)


def verify_record(row, *, replay=True):
    report = {"protocol": PROTOCOL, "passed": False}
    try:
        validate(row)
    except (ValueError, TypeError, KeyError) as error:
        return dict(report, reason="schema", detail=str(error))
    report["record_sha256"] = record_hash(row)
    teacher = row["teacher"]
    report["finish_reason_retained"] = teacher.get("finish_reason") is not None
    if teacher.get("truncated") or any(teacher.get(k) in LENGTH_REASONS
                                       for k in ("finish_reason", "stop_reason", "native_finish_reason")):
        return dict(report, reason="truncated")
    think, answer = split_response(row["messages"][-1]["content"])
    if not think.strip():
        return dict(report, reason="missing_reasoning")
    prediction = last_boxed(answer)
    if not prediction:
        return dict(report, reason="missing_final_box")
    program = row["program"]
    unit = evaluate({"mode": "unit", **program}) if replay else row["unit_test_result"]
    report["unit_tests"] = unit
    if unit.get("status") != "passed":
        return dict(report, reason="unit_tests")
    execution = evaluate({"mode": "execute", **program, "parameters": row["parameters"]}) if replay else row["execution"]
    report["execution"] = execution
    if execution.get("status") != "ok":
        return dict(report, reason="execution")
    reference = evaluate({"mode": "compare", "actual": execution["value"],
                          "expected": row["reference"]["value"], "rtol": 1e-9, "zero_atol": 1e-12})
    report["reference_check"] = reference
    if reference.get("status") != "ok" or not reference.get("match"):
        return dict(report, reason="reference_mismatch")
    comparison = evaluate({"mode": "compare", "actual": prediction,
                           "expected": execution["value"], "rtol": .05, "zero_atol": 1e-12})
    report["answer_check"] = comparison
    report["final_boxed"] = prediction
    if comparison.get("status") != "ok" or not comparison.get("match"):
        return dict(report, reason="answer_mismatch")
    return dict(report, passed=True, reason="ok")


def run(item):
    item["verification"] = verify_record(item, replay=False)
    if not item["verification"]["passed"]:
        raise ValueError("Answer rejected: " + item["verification"]["reason"])
    return item

