"""Single-model API calls with bounded retries and per-step response caching."""

import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
import httpx
from steps import digest, write_json
from steps.format_answers import split_response, last_boxed


def json_response(text):
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def boolean_response(text):
    answer = text.strip().strip("`").strip().lower()
    if answer not in ("true", "false"):
        raise ValueError("Expected True or False")
    return answer == "true"


def judgement_response(text):
    match = re.search(r"(?:结论|conclusion)\s*[:：]\s*(YES|NO)\b", text, re.I)
    answer = match[1].upper() if match else text.strip().upper()
    if answer not in ("YES", "NO"):
        raise ValueError("Expected a YES/NO conclusion")
    return answer == "YES"


class CallError(RuntimeError):
    pass


class Client:
    def __init__(self, config, output):
        self.config = config
        self.model = config["model"]
        self.url = os.environ.get("TIRE_BASE_URL", "").rstrip("/")
        self.key = os.environ.get("TIRE_API_KEY", "")
        url = urlsplit(self.url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query:
            raise ValueError("Set TIRE_BASE_URL to a valid API base URL including /v1")
        if not self.key:
            raise ValueError("Set TIRE_API_KEY; for an unauthenticated local server, "
                             "set the literal value 'EMPTY', not an empty string")
        self.cache = Path(output) / "calls"
        self.http = httpx.Client(trust_env=False, follow_redirects=False,
                                 timeout=httpx.Timeout(1800, connect=30))
        self.calls_made = 0
        self.cached_calls = 0

    def close(self):
        self.http.close()

    def _request(self, payload):
        content, reasoning, finish, model, usage = [], [], None, None, {}
        size = 0
        with self.http.stream("POST", self.url + "/chat/completions", json=payload,
                              headers={"Authorization": "Bearer " + self.key}) as response:
            if response.is_error:
                response.read()
            response.raise_for_status()
            if "text/event-stream" not in response.headers.get("content-type", ""):
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2 * 1024 * 1024:
                        raise ValueError("Response exceeds 2 MiB")
                data = json.loads(raw)
                choice = data["choices"][0]; message = choice["message"]
                return {"content": message.get("content") or "",
                        "reasoning": message.get("reasoning_content") or message.get("reasoning") or "",
                        "finish_reason": choice.get("finish_reason"), "response_model": data.get("model"),
                        "usage": data.get("usage") or {}}
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                part = line[5:].strip()
                if part == "[DONE]":
                    break
                data = json.loads(part)
                if data.get("error"):
                    raise ValueError("Provider returned an error chunk")
                model = data.get("model") or model
                usage = data.get("usage") or usage
                choices = data.get("choices") or []
                if not choices:
                    continue
                if len(choices) != 1 or choices[0].get("index", 0) != 0:
                    raise ValueError("Expected one completion")
                choice = choices[0]; delta = choice.get("delta") or {}
                c = delta.get("content") or ""
                r = delta.get("reasoning_content") or delta.get("reasoning") or ""
                size += len(c) + len(r)
                if size > 2 * 1024 * 1024:
                    raise ValueError("Response exceeds 2 MiB")
                content.append(c); reasoning.append(r)
                finish = choice.get("finish_reason") or finish
        return {"content": "".join(content), "reasoning": "".join(reasoning),
                "finish_reason": finish, "response_model": model, "usage": usage}

    def complete(self, sample_id, stage, prompt, *, parse=None, teacher=False):
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                   "temperature": self.config.get("temperature", .6),
                   "max_tokens": self.config.get("max_tokens", 28000), "n": 1,
                   "stream": True, "stream_options": {"include_usage": True},
                   "enable_thinking": True}
        fingerprint = digest({"payload": payload, "endpoint_sha256": digest(self.url)})
        path = self.cache / (digest([sample_id, stage])[:24] + ".json")
        print(f"[{sample_id}] {stage}", flush=True)
        if path.exists():
            cached = json.loads(path.read_text())
            if cached["fingerprint"] != fingerprint:
                raise ValueError("Cached request changed; choose a new output directory")
            result = cached["response"]
            self.cached_calls += 1
            if parse:
                result["parsed"] = parse(result["answer"])
            return result
        last_error = "incomplete_response"
        for attempt in range(2):
            started = time.monotonic(); result = None
            try:
                self.calls_made += 1
                result = self._request(payload)
                if result["response_model"] and result["response_model"].casefold() != self.model.casefold():
                    raise CallError("Provider returned a different model identifier")
                if result["finish_reason"] != "stop":
                    raise ValueError("Response did not terminate normally")
                think, answer = split_response(result["content"], result["reasoning"])
                if not answer.strip():
                    raise ValueError("Missing final response")
                if teacher and not last_boxed(answer):
                    raise ValueError("Missing final boxed answer")
                parsed = parse(answer) if parse else None
                result.update(think=think, answer=answer, requested_model=self.model,
                              elapsed_seconds=round(time.monotonic() - started, 3), attempts=attempt + 1)
                write_json(path, {"sample_id": sample_id, "stage": stage, "fingerprint": fingerprint,
                                  "request": payload, "response": result})
                if parse:
                    result["parsed"] = parsed
                return result
            except httpx.HTTPStatusError as error:
                code = error.response.status_code; last_error = f"HTTP {code}"
                try:
                    raw_error = error.response.read().decode(errors="replace")[:2000]
                except (httpx.HTTPError, httpx.StreamError):
                    raw_error = "Response body unavailable"
                raw_error = raw_error.replace(self.key, "<redacted>").replace(self.url, "<endpoint>")
                raw_error = re.sub(r"https?://\S+|sk-[A-Za-z0-9_-]{10,}|\b[A-Za-z0-9_-]{32,}\b", "<redacted>", raw_error)
                write_json(path.with_suffix(f".http-{code}.json"),
                           {"stage": stage, "fingerprint": fingerprint, "request": payload,
                            "status_code": code, "error_body": raw_error})
                if code not in (408, 429) and code < 500:
                    raise CallError(last_error + "; check endpoint/model/credentials") from None
            except (httpx.RequestError, ValueError, TypeError, KeyError, IndexError) as error:
                last_error = type(error).__name__
            write_json(path.with_suffix(f".attempt-{attempt + 1}.json"),
                       {"stage": stage, "fingerprint": fingerprint, "request": payload,
                        "response": result, "error": last_error})
            if attempt == 0:
                time.sleep(2)
        raise CallError(f"{stage}: failed after 2 attempts ({last_error})")
