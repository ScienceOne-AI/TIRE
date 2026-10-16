"""Construct, filter and normalize the question using the Appendix C.1 prompts."""

import json
import prompts
from client import json_response, judgement_response


def run(item, client):
    values = prompts.formula_values(item["formula"], escaped=True)
    values.update(function_code=item["program"]["code"],
                  param_list="\n".join(f"- {k}: {v}" for k, v in item["parameters"].items()),
                  answer_para=json.dumps({"sought_quantity": item["reference"]["value"]}, ensure_ascii=False, indent=2))
    prompt = prompts.render(prompts.QUESTIONS, values)
    problem = client.complete(item["id"], "questions", prompt, parse=json_response)["parsed"]
    question, unit = problem["question"], problem["answer_units"]
    if not isinstance(question, str) or not question.strip() or not isinstance(unit, str) or not unit.strip():
        raise ValueError("Missing question or answer unit")
    check_prompt = prompts.render(prompts.QUESTION_FILTER, {"question": question.strip()})
    check = client.complete(item["id"], "question_filter", check_prompt, parse=judgement_response)
    if not check["parsed"]:
        raise ValueError("Question rejected by plausibility filter")
    normalized = client.complete(item["id"], "normalize", prompts.render(prompts.NORMALIZE, {"text": question}))
    item["problem"] = normalized["answer"].strip()
    item["reference"]["unit"] = unit
    return item
