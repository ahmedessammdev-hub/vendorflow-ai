"""Run local gates and generate the report and its README excerpt from the same evidence."""

import json
import os
import platform
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".runtime/metrics"
BACK = ROOT / "backend"
FRONT = ROOT / "frontend"
COMMANDS: list[tuple[str, str, int]] = []
ROWS: list[tuple[str, str, str, str]] = []


def run(directory: Path, args: list[str], label: str) -> str:
    binary = shutil.which(args[0])
    if not binary:
        raise RuntimeError(f"Missing {args[0]}")
    print("Running", " ".join(args), flush=True)
    proc = subprocess.run(
        [binary, *args[1:]],
        cwd=directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        env=os.environ
        | {
            "PYTHONUTF8": "1",
            "NO_COLOR": "1",
            "VENDORFLOW_SCREENSHOTS": str(OUT / "screenshots"),
        },
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout)
    (OUT / (label + ".txt")).write_text(output, encoding="utf-8")
    COMMANDS.append((str(directory.relative_to(ROOT)), " ".join(args), proc.returncode))
    if proc.returncode:
        raise RuntimeError(f"{label} exited {proc.returncode}\n{output[-3500:]}")
    return output


def row(name: str, value: object, target: str, passed: bool | None = None) -> None:
    ROWS.append(
        (
            name,
            str(value),
            target,
            "Reported" if passed is None else "PASS" if passed else "MISS",
        )
    )


def match(pattern: str, source: str) -> int:
    found = re.search(pattern, source, re.MULTILINE)
    if not found:
        raise ValueError(f"Missing measurement {pattern}")
    return int(found[1])


def table(rows: list[tuple[str, str, str, str]]) -> str:
    return (
        "| Metric | Measured value | Target | Status |\n|---|---|---|---|\n"
        + "\n".join("| " + " | ".join(r) + " |" for r in rows)
        + "\n"
    )


def collect() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sha = run(ROOT, ["git", "rev-parse", "HEAD"], "sha").strip()
    node = run(ROOT, ["node", "-v"], "node").strip()
    for args in [
        ["ruff", "check", ".", "../scripts"],
        ["ruff", "format", "--check", ".", "../scripts"],
        ["mypy", "app"],
    ]:
        run(BACK, ["uv", "run", *args], "-".join(args[:2]))
    for args in [["alembic", "upgrade", "head"], ["alembic", "check"]]:
        run(BACK, ["uv", "run", *args], "migration-" + args[1])
    suite = run(
        BACK,
        [
            "uv",
            "run",
            "pytest",
            "-q",
            "-s",
            "--cov=app",
            "--cov-report=term-missing",
            "--junitxml=../.runtime/metrics/backend.xml",
        ],
        "pytest",
    )
    run(
        BACK,
        ["uv", "run", "coverage", "json", "-o", "../.runtime/metrics/coverage.json"],
        "coverage",
    )
    xml = ET.parse(OUT / "backend.xml")
    cases = xml.findall(".//testcase")
    passed = [
        c
        for c in cases
        if not any(c.find(k) is not None for k in ("failure", "error", "skipped"))
    ]
    passed_names = {c.attrib["name"].split("[")[0] for c in passed}
    covered = {
        i
        for i in range(1, 12)
        if i != 8 and any(f"vf{i:02}" in n for n in passed_names)
    }
    row("Automated VF criteria", f"{len(covered)}/10", "10/10", len(covered) == 10)
    row(
        "Backend tests",
        f"{len(passed)}/{len(cases)}",
        "all pass",
        len(passed) == len(cases),
    )
    guard = match(r"Jira creates before persisted approval: (\d+)", suite)
    row("Pre-approval Jira creates", guard, "0", guard == 0)
    seq = match(r"Property sequences completed: (\d+)", suite)
    row("Property-test sequences", seq, ">=500", seq >= 500)
    faults = ["401", "429", "500", "timeout", "reset"]
    found = sum(
        any(
            "delivery_matrix" in c.attrib["name"] and "[" + f + "-" in c.attrib["name"]
            for c in passed
        )
        for f in faults
    ) + int(any("crash_after_remote_create" in n for n in passed_names))
    row("Fault paths exercised", f"{found}/6", "6/6", found == 6)
    cov = json.loads((OUT / "coverage.json").read_text())
    total = cov["totals"]["percent_covered"]
    domain = [
        v["summary"]
        for k, v in cov["files"].items()
        if "/domain/" in k.replace("\\", "/")
    ]
    dc = (
        100
        * sum(v["covered_lines"] for v in domain)
        / sum(v["num_statements"] for v in domain)
    )
    row("Coverage, overall", f"{total:.1f}%", "≥85%", total >= 85)
    row("Coverage, domain", f"{dc:.1f}%", "≥95%", dc >= 95)
    run(FRONT, ["npm", "run", "gen:api"], "schema")
    run(FRONT, ["npm", "run", "lint"], "eslint")
    row("Lint and type errors", 0, "0", True)
    unit = run(FRONT, ["npm", "test", "--", "--watch=false"], "vitest")
    units = match(r"Tests\s+(\d+) passed", unit)
    row("Frontend tests", f"{units} passed", "0 failures", True)
    run(FRONT, ["npm", "run", "build"], "build")
    dist = FRONT / "dist/vendorflow/browser"
    scripts = re.findall(
        r'<script[^>]*\bsrc="([^"]+\.js)"',
        (dist / "index.html").read_text(encoding="utf-8"),
    )
    if not scripts:
        raise ValueError("Missing initial JS bundle")
    row(
        "Initial JavaScript",
        f"{sum((dist / f).stat().st_size for f in scripts):,} bytes",
        "report",
    )
    e2e = run(FRONT, ["npx", "playwright", "test"], "browser")
    journeys = match(r"(\d+) passed \(", e2e)
    row("Browser journeys", f"{journeys}/2", "2/2", journeys == 2)
    axe = re.findall(r"axe ([\w-]+) serious/critical (\d+)", e2e)
    findings = sum(int(v) for _, v in axe)
    row(
        "Serious/critical axe findings",
        f"{findings} on {len(axe)} screens",
        "0 on ≥4",
        findings == 0 and len(axe) >= 4,
    )
    smoke = run(
        ROOT,
        ["uv", "run", "--project", "backend", "python", "scripts/verify_workflow.py"],
        "smoke",
    )
    row(
        "Paused review survives real server restart",
        "PASS" if "VF-06 PASS" in smoke else "FAIL",
        "pass",
        "VF-06 PASS" in smoke,
    )
    load = json.loads(
        run(
            ROOT,
            [
                "uv",
                "run",
                "--project",
                "backend",
                "python",
                "scripts/load_test.py",
                "--race",
                "50",
            ],
            "load",
        )
    )
    race = load["race"]
    row(
        "50 concurrent approvals",
        f"{race['accepted']} accepted, {race['conflicts']} conflicts, {race['operations']} operation, {race['create_calls']} create, {race['issues']} issue",
        "1 operation and 1 create",
        race["operations"] == race["create_calls"] == race["issues"] == 1,
    )
    for name, m in load["latencies"].items():
        limit = (
            1000
            if name == "submit_to_pause"
            else 200
            if name in ("create", "decision")
            else 100
        )
        row(
            "API " + name,
            f"p50 {m['p50_ms']} / p95 {m['p95_ms']} ms",
            f"p95 < {limit} ms",
            m["p95_ms"] < limit,
        )
    eval_path = ROOT / "docs/evaluation.json"
    ev = json.loads(eval_path.read_text(encoding="utf-8")) if eval_path.exists() else {}
    attempted = ev.get("attempted", 0)
    complete = attempted == 20
    reason = ev.get("stop_reason") or "No saved live evaluation"
    if complete:
        for title, k, threshold in [
            ("First-pass schema validity", "first_schema", None),
            ("Schema validity after repair", "final_schema", 0.95),
            ("Grounded recommendation per case", "grounded", 1),
            ("Label agreement", "agreement", None),
        ]:
            score = ev[k] / attempted
            row(
                title,
                f"{ev[k]}/{attempted} ({score:.1%})",
                f"≥{threshold:.0%}" if threshold else "report",
                score >= threshold if threshold else None,
            )
        row(
            "Injection cases",
            f"{ev['adversarial_pass']}/3",
            "3/3",
            ev["adversarial_pass"] == 3,
        )
    else:
        for title, target in [
            ("First-pass schema validity", "report"),
            ("Schema validity after repair", "≥95%"),
            ("Grounded recommendation per case", "100%"),
            ("Label agreement", "report"),
            ("Injection cases", "3/3"),
        ]:
            row(title, "NOT MEASURED on full set — " + reason, target)
    for name, vals in ev.get("latencies", {}).items():
        row(
            "Live " + name + " attempt latency",
            f"p50 {vals['p50_ms']} / p95 {vals['p95_ms']} ms",
            "report",
        )
    pauses = [
        c["submit_to_pause_ms"]
        for c in ev.get("cases", [])
        if c.get("submit_to_pause_ms") is not None
    ]
    row(
        "Live submit to human pause",
        f"{sum(pauses) / len(pauses):.1f} ms mean ({len(pauses)} cases)"
        if pauses
        else "NOT MEASURED — no end-to-end timer in saved trial",
        "report",
    )
    ti, to = ev.get("tokens_in"), ev.get("tokens_out")
    row(
        "Live tokens per attempted case",
        f"{ti / attempted:.1f} input / {to / attempted:.1f} output"
        if ti is not None and to is not None and attempted
        else "NOT MEASURED — usage unavailable",
        "report",
    )
    cost = ev.get("total_cost_usd")
    row(
        "Live cost per attempted case",
        f"USD {cost / attempted:.6f}"
        if cost is not None and attempted
        else "NOT MEASURED — verified prices or usage unavailable",
        "report",
    )
    row("VF-08 real Jira", "SKIPPED — no authorized live Jira site or issue", "opt-in")
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    meta = f"Generated {stamp} at commit `{sha}`. {platform.platform()}, {platform.machine()}, Python {platform.python_version()}, Node {node}.\n\n"
    meta += f"Local gates use Jira simulation. Randomized tests and load measurements use offline or fixture AI. Load measurements use {load['samples']} observations per endpoint through in-process ASGI and include background work. The separate live evaluation used {ev.get('model', 'no model')} at `{ev.get('sha', 'unavailable')}`, {attempted}/20 cases attempted.\n\n"
    report = "# VendorFlow verification and measurements\n\n" + meta + table(ROWS)
    report += (
        "\n## Live label confusion counts\n\n"
        + (
            "\n".join(f"- {k}: {v}" for k, v in sorted(ev.get("confusion", {}).items()))
            or "NOT MEASURED"
        )
        + "\n\nAgreement on these hand-labeled synthetic cases is a sanity check. Unknown usage and prices remain unmeasured.\n"
    )
    report += (
        "\n## Commands\n\n| Directory | Command | Exit |\n|---|---|---|\n"
        + "".join(f"| {d} | `{cmd}` | {code} |\n" for d, cmd, code in COMMANDS)
    )
    (ROOT / "docs/metrics.md").write_text(report, encoding="utf-8")
    test_report = (
        "# Acceptance evidence\n\n"
        + meta
        + "| ID | Result | Executed evidence |\n|---|---|---|\n"
    )
    for i in range(1, 12):
        names = sorted(n for n in passed_names if f"vf{i:02}" in n)
        result = (
            "SKIPPED live"
            if i == 8
            else "PASS offline"
            if i in covered
            else "NOT MEASURED"
        )
        evidence = (
            ", ".join("`" + n + "`" for n in names)
            or "Requires explicit approval for one issue in a test project."
        )
        if i == 4:
            evidence += ". See the separate live results in [metrics](metrics.md)."
        test_report += f"| VF-{i:02} | {result} | {evidence} |\n"
    test_report += "\n[Commands, exit codes and measured targets](metrics.md) · [Browser captures](screenshots/)\n"
    (ROOT / "docs/test-report.md").write_text(test_report, encoding="utf-8")
    readme = ROOT / "README.md"
    content = readme.read_text(encoding="utf-8")
    start, end = "<!-- metrics:start -->", "<!-- metrics:end -->"
    first, tail = content.split(start, 1)
    _, last = tail.split(end, 1)
    summary = [
        r
        for r in ROWS
        if r[0]
        in {
            "Backend tests",
            "Coverage, overall",
            "Browser journeys",
            "Pre-approval Jira creates",
            "50 concurrent approvals",
            "Schema validity after repair",
        }
    ]
    readme.write_text(
        first + start + "\n\n" + table(summary) + "\n" + end + last, encoding="utf-8"
    )
    print("Reports saved to docs/metrics.md and docs/test-report.md", flush=True)


if __name__ == "__main__":
    collect()
