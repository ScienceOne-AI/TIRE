"""Compute the reference by executing the formula, independently of the teacher."""

from sandbox import evaluate


def run(item):
    result = evaluate({"mode": "execute", **item["program"], "parameters": item["parameters"]})
    if result.get("status") != "ok":
        raise ValueError("Formula execution failed: " + str(result))
    item["execution"] = result
    item["reference"] = {"value": result["value"], "unit": None}
    return item
