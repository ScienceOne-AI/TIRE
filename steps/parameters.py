"""Generate parameters and optionally apply the historical seeded perturbation."""

import random
import prompts
from client import json_response


def perturb(parameters, seed):
    rng = random.Random(seed)

    def change(value, in_list=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if value == 0 and in_list:
                return value
            new = rng.uniform(0, .0005) if value == 0 else value * (1 + rng.uniform(-.05, .05))
            rounded = round(new, 3)
            return new if rounded == 0 and new != 0 else rounded
        if isinstance(value, list):
            return [change(x, True) for x in value]
        return value

    return {k: change(v) for k, v in parameters.items()}


def run(item, client, *, apply_perturbation=False, seed=42):
    values = prompts.formula_values(item["formula"], escaped=True)
    values["function_code"] = item["program"]["code"]
    prompt = prompts.render(prompts.PARAMETERS, values)
    params = client.complete(item["id"], "parameters", prompt, parse=json_response)["parsed"]["input_para"]
    if not isinstance(params, dict):
        raise ValueError("input_para must be an object")
    item["parameters"] = perturb(params, seed) if apply_perturbation else params
    item["provenance"]["parameter_perturbation"] = apply_perturbation
    return item
