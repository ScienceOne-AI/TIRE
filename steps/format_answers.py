"""Separate reasoning, retain the final response, and extract only its last box."""

import re


def split_response(content, reasoning=""):
    if "</think>" in content:
        before, final = content.rsplit("</think>", 1)
        start = before.find("<think>")
        return before[start + 7:] if start >= 0 else before, final
    if "<think>" in content:
        return content.split("<think>", 1)[1], ""
    return reasoning, content


def last_boxed(answer):
    _, final = split_response(answer)
    matches = list(re.finditer(r"\\boxed\b", final))
    if not matches:
        return ""
    pos = matches[-1].end()
    while pos < len(final) and final[pos].isspace():
        pos += 1
    if pos >= len(final) or final[pos] != "{":
        return ""
    start, depth = pos + 1, 1
    for i in range(start, len(final)):
        if final[i] == "{" and final[i - 1] != "\\":
            depth += 1
        elif final[i] == "}" and final[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return final[start:i].strip()
    return ""


def run(item):
    result = item.pop("teacher_response")
    think, answer = result["think"], result["answer"]
    assistant = "<think>\n" + think.strip() + "\n</think>\n" + answer.strip()
    item["messages"] = [{"role": "user", "content": item["question"]},
                        {"role": "assistant", "content": assistant}]
    item["final_boxed"] = last_boxed(answer)
    return item
