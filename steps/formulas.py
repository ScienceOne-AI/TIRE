"""Extract and filter formulas as specified in Appendix C.1."""

import json
import prompts
from client import json_response, boolean_response


def extract(source, sample_id, client):
    if "formula" in source:
        values = [source["formula"]]
    else:
        text = source.get("text", "").strip()
        if not text:
            raise ValueError("Provide a formula object or source text")
        prompt = prompts.render(prompts.FORMULAS, {"problem_text": text,
                                                   "problem_solutions": source.get("solution", "")})
        values = client.complete(sample_id, "formulas", prompt, parse=json_response)["parsed"]
    if not isinstance(values, list) or not values:
        raise ValueError("Formula extraction must return a nonempty array")
    formulas = []
    for value in values:
        formula = {"name": value["name"], "expression": value.get("expression", value.get("formula")),
                   "description": value.get("description", ""), "domain": value.get("domain", value.get("applicable_range"))}
        if not all(isinstance(formula[k], str) and formula[k].strip() for k in ("name", "expression", "domain")):
            raise ValueError("Formula needs name, expression and applicability domain")
        formulas.append(formula)
    return formulas


def run(item, client):
    formula_json = json.dumps(prompts.formula_values(item["formula"]), ensure_ascii=False, indent=2)
    prompt = prompts.render(prompts.FORMULA_FILTER, {"formula_record": formula_json})
    if not client.complete(item["id"], "formula_filter", prompt, parse=boolean_response)["parsed"]:
        raise ValueError("Formula rejected by plausibility filter")
    return item
