"""Run the TIRE data-construction steps with one model and one command."""

import argparse
import fcntl
import json
from pathlib import Path
import prompts
from client import Client, CallError
from sandbox import preflight, IsolationError
from steps import read_jsonl, write_json, digest
from steps import formulas, code, unit_tests, parameters, calculate, questions
from steps import distill, format_answers, verify, export


def run(input_path, config_path, output, *, limit=None, seed=42, perturb=False):
    sources = read_jsonl(input_path)
    if not sources or limit is not None and limit < 1:
        raise ValueError("Provide nonempty inputs and a positive limit")
    config = json.loads(Path(config_path).read_text())
    if set(config) - {"model", "temperature", "max_tokens"}:
        raise ValueError("Configuration accepts only model, temperature and max_tokens")
    preflight()
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    client = Client(config, output)
    try:
        with (output / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fingerprint = digest({"inputs": sources, "config": config, "prompts": prompts.PROMPT_SHA256,
                                  "prompt_version": prompts.PROMPT_VERSION,
                                  "endpoint_sha256": digest(client.url), "seed": seed, "perturb": perturb, "limit": limit})
            manifest = output / "run.json"
            if manifest.exists() and json.loads(manifest.read_text())["fingerprint"] != fingerprint:
                raise ValueError("Run configuration changed; use a new output directory")
            write_json(manifest, {"fingerprint": fingerprint, "model": client.model, "seed": seed,
                                  "perturb": perturb, "prompt_version": prompts.PROMPT_VERSION,
                                  "prompt_sha256": prompts.PROMPT_SHA256})
            accepted, rejected, used_questions, used_instances = [], [], set(), set()
            attempted = 0
            for source_index, source in enumerate(sources):
                if limit is not None and attempted >= limit:
                    break
                source_id = digest([source_index, source])[:20]
                try:
                    found = formulas.extract(source, source_id, client)
                except (CallError, ValueError, KeyError, TypeError) as error:
                    rejected.append({"id": source_id, "stage": "formulas", "error": str(error)})
                    attempted += 1
                    continue
                for formula_index, formula in enumerate(found):
                    if limit is not None and attempted >= limit:
                        break
                    attempted += 1
                    sample_id = "tire-" + digest([source_id, formula_index])[:20]
                    formula["id"] = digest([formula["name"], formula["expression"]])
                    item = {"schema_version": 1, "id": sample_id, "formula": formula,
                            "provenance": {"source_dataset": source.get("source_dataset", "user-supplied"),
                                           "source_id": source.get("id"), "source_sha256": digest(source),
                                           "prompt_version": prompts.PROMPT_VERSION},
                            "rights": {"status": "pending", "reason": "Review source/API output rights before publication"}}
                    stage = "formula_filter"
                    try:
                        formulas.run(item, client)
                        stage = "code"; code.run(item, client)
                        stage = "unit_tests"; unit_tests.run(item, client)
                        stage = "parameters"; parameters.run(item, client, apply_perturbation=perturb, seed=seed + attempted - 1)
                        stage = "calculate"; print(f"[{sample_id}] {stage}", flush=True); calculate.run(item)
                        stage = "questions"; questions.run(item, client)
                        stage = "distill"; distill.run(item, client, seed=seed)
                        stage = "format_answers"; format_answers.run(item)
                        stage = "verify"; print(f"[{sample_id}] {stage}", flush=True); verify.run(item)
                        instance = digest([formula["id"], item["parameters"]])
                        if item["question"].strip() in used_questions or instance in used_instances:
                            raise ValueError("Duplicate question or formula instance")
                        used_questions.add(item["question"].strip()); used_instances.add(instance)
                        accepted.append(item)
                    except IsolationError:
                        raise
                    except (CallError, ValueError, KeyError, TypeError, SyntaxError) as error:
                        rejected.append({"id": sample_id, "stage": stage, "error": str(error), "sample": item})
                    export.run(accepted, output)
                    write_json(output / "rejected.jsonl", rejected, lines=True)
            export.run(accepted, output)
            write_json(output / "rejected.jsonl", rejected, lines=True)
            summary = {"attempted": attempted, "accepted": len(accepted), "rejected": len(rejected),
                       "model": client.model, "api_requests": client.calls_made, "cached_steps": client.cached_calls}
            write_json(output / "summary.json", summary)
            return summary
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.example.json"))
    parser.add_argument("--limit", type=int, help="Maximum formula instances attempted")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--perturb", action="store_true", help="Apply seeded historical +/-5 percent perturbation")
    args = parser.parse_args()
    try:
        summary = run(args.input, args.config, args.output, limit=args.limit, seed=args.seed, perturb=args.perturb)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(summary, indent=2))
    return 1 if summary["rejected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
