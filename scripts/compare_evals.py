"""Summarize archived evaluation results without calling a provider."""

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def describe(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    rows = report["cases"]
    calls = [call for case in rows for call in case["calls"]]
    matched = sum(case["expected"] == case["label"] for case in rows)
    usable = sum(case["label"] is not None for case in rows)
    return {
        "file": path.name,
        "revision": report["sha"],
        "requested_model": report["model"],
        "prompt_version": report.get("prompt_version"),
        "dataset_sha256": report.get("dataset_sha256"),
        "attempted": len(rows),
        "complete_assessments": sum(case["status"] == "OK" for case in rows),
        "valid_summaries": sum(
            any(
                c["node"] == "intake_summary" and c["outcome"] == "OK"
                for c in case["calls"]
            )
            for case in rows
        ),
        "valid_recommendations": usable,
        "matches": matched,
        "agreement_all": [matched, len(rows)],
        "agreement_when_recommendation_available": [matched, usable],
        "outcomes_by_attempt": dict(Counter(c["outcome"] for c in calls)),
        "reasons_for_failed_attempts": dict(
            Counter(
                c.get("failure_reason") or "unrecorded"
                for c in calls
                if c["outcome"] != "OK"
            )
        ),
        "models_on_successful_attempts": dict(
            Counter(c["model"] for c in calls if c["outcome"] == "OK")
        ),
        "mismatches": [
            {"id": c["id"], "expected": c["expected"], "returned": c["label"]}
            for c in rows
            if c["label"] is not None and c["label"] != c["expected"]
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", type=Path, nargs="+")
    print(json.dumps([describe(p) for p in parser.parse_args().reports], indent=2))
