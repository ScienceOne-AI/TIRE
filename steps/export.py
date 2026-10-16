"""Export accepted records to SFT and GRPO JSONL; no additional command needed."""

from pathlib import Path
from steps import write_json, digest
from steps.verify import validate, record_hash, PROTOCOL


def export_rows(rows, output, *, allow_pending=False):
    output = Path(output)
    sft, grpo, ids = [], [], set()
    for row in rows:
        validate(row)
        if row["id"] in ids:
            raise ValueError("Duplicate sample ID")
        ids.add(row["id"])
        verification = row.get("verification", {})
        if (not verification.get("passed") or verification.get("protocol") != PROTOCOL
                or verification.get("record_sha256") != record_hash(row)):
            raise ValueError("Sample was changed or did not pass verification")
        if row["rights"]["status"] != "approved" and not allow_pending:
            raise ValueError("Historical sample rights are pending")
        sft.append({"messages": row["messages"]})
        grpo.append({"messages": row["messages"][:-1],
                     "solution": "\\boxed{" + str(row["reference"]["value"]) + "}",
                     "meta": {"sample_id": row["id"]}})
    write_json(output / "sft.jsonl", sft, lines=True)
    write_json(output / "grpo.jsonl", grpo, lines=True)
    manifest = {"count": len(rows), "ids": sorted(ids), "record_set_sha256": digest(rows),
                "public_release_ready": bool(rows) and all(r["rights"]["status"] == "approved" for r in rows)}
    write_json(output / "manifest.json", manifest)
    return manifest


def run(rows, output):
    write_json(Path(output) / "samples.jsonl", rows, lines=True)
    return export_rows(rows, output, allow_pending=True)
