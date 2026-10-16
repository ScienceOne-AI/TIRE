"""Ask the same Qwen model to solve the question without the execution reference."""

import prompts


def run(item, client, *, seed=42):
    sentence_seed = f"{seed}:{item['id']}"
    question = prompts.teacher(item["problem"], item["reference"]["unit"], seed=sentence_seed)
    response = client.complete(item["id"], "distill", question, teacher=True)
    item["question"] = question
    item["teacher"] = {"model": response["requested_model"], "response_model": response["response_model"],
                       "finish_reason": response["finish_reason"], "usage": response["usage"],
                       "temperature": client.config.get("temperature", .6),
                       "max_tokens": client.config.get("max_tokens", 28000),
                       "unit_sentence_seed": sentence_seed}
    item["teacher_response"] = response
    return item
