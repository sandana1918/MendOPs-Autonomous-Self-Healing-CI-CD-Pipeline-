"""MendOps benchmark harness.

Runs three measurements and writes machine- and human-readable reports:

1. Security recall      - share of malicious payloads the AST guard blocks.
2. False-positive rate  - share of benign patches the guard wrongly blocks.
3. Pipeline oracle      - for each seeded bug, proves the buggy code fails its
                          tests and the reference fix passes through the full
                          guard + sandbox path, with per-patch latency.

Offline by default (local sandbox, no Docker, no API key). Add ``--llm`` to
also measure how often the configured model fixes each bug end-to-end.

    python benchmark/run.py
    python benchmark/run.py --llm        # requires AI_API_KEY in .env
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Local backend keeps the benchmark runnable on any machine (no Docker daemon).
os.environ.setdefault("SANDBOX_BACKEND", "local")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.guards import verify_patch  # noqa: E402
from app.sandbox import ASSERTION_MARKER, run_files_in_sandbox  # noqa: E402
from corpus import BENIGN_PATCHES, BUG_CASES, MALICIOUS_PATCHES  # noqa: E402


def evaluate_security() -> dict:
    blocked = [name for name, code in MALICIOUS_PATCHES.items() if not verify_patch(code).ok]
    allowed = [name for name, code in BENIGN_PATCHES.items() if verify_patch(code).ok]
    false_positives = [name for name, code in BENIGN_PATCHES.items() if not verify_patch(code).ok]
    return {
        "malicious_total": len(MALICIOUS_PATCHES),
        "malicious_blocked": len(blocked),
        "block_rate": len(blocked) / len(MALICIOUS_PATCHES),
        "benign_total": len(BENIGN_PATCHES),
        "benign_allowed": len(allowed),
        "false_positives": false_positives,
        "false_positive_rate": len(false_positives) / len(BENIGN_PATCHES),
    }


def evaluate_pipeline(work_dir: Path) -> dict:
    rows = []
    latencies = []
    for case in BUG_CASES:
        target = work_dir / f"{case.id}_target.py"
        target.write_text(f"# fixture\n\n{ASSERTION_MARKER}\n{case.tests.lstrip()}", encoding="utf-8")
        target_key = str(target).replace("\\", "/")

        buggy_fails = not run_files_in_sandbox({target_key: case.buggy}, target_key)["success"]
        guard_ok = verify_patch(case.fixed).ok

        start = time.perf_counter()
        fixed_passes = run_files_in_sandbox({target_key: case.fixed}, target_key)["success"]
        latency_ms = (time.perf_counter() - start) * 1000
        latencies.append(latency_ms)

        oracle_valid = buggy_fails and fixed_passes and guard_ok
        rows.append(
            {
                "id": case.id,
                "category": case.category,
                "buggy_fails": buggy_fails,
                "guard_ok": guard_ok,
                "fixed_passes": fixed_passes,
                "oracle_valid": oracle_valid,
                "latency_ms": round(latency_ms, 1),
            }
        )

    valid = [r for r in rows if r["oracle_valid"]]
    return {
        "cases": len(rows),
        "oracle_valid": len(valid),
        "oracle_rate": len(valid) / len(rows),
        "categories": sorted({r["category"] for r in rows}),
        "median_latency_ms": round(statistics.median(latencies), 1),
        "p95_latency_ms": round(_percentile(latencies, 95), 1),
        "rows": rows,
    }


def evaluate_llm(work_dir: Path) -> dict:
    from app.agent import generate_patch
    from app.config import settings

    async def fix_case(case) -> dict:
        target = work_dir / f"{case.id}_llm.py"
        target.write_text(f"# fixture\n\n{ASSERTION_MARKER}\n{case.tests.lstrip()}", encoding="utf-8")
        target_key = str(target).replace("\\", "/")
        context = f"File: {target_key}\n{case.buggy}"
        feedback = ""
        start = time.perf_counter()
        for attempt in range(1, settings.MAX_PATCH_ATTEMPTS + 1):
            patch = await generate_patch(case.title, case.body, context, feedback=feedback)
            if not patch:
                break
            files = patch.file_map(target_key)
            guard_errors = [e for f in files.values() if not verify_patch(f).ok for e in verify_patch(f).errors]
            if guard_errors:
                feedback = f"Attempt {attempt} blocked by guard: {'; '.join(guard_errors)}"
                continue
            result = run_files_in_sandbox(files, target_key)
            if result["success"]:
                return {"id": case.id, "solved": True, "attempts": attempt, "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
            feedback = f"Attempt {attempt} failed tests: {result['logs'][:300]}"
        return {"id": case.id, "solved": False, "attempts": settings.MAX_PATCH_ATTEMPTS, "latency_ms": round((time.perf_counter() - start) * 1000, 1)}

    async def run_all():
        return [await fix_case(case) for case in BUG_CASES]

    rows = asyncio.run(run_all())
    solved = [r for r in rows if r["solved"]]
    return {
        "model": settings.MODEL_NAME,
        "cases": len(rows),
        "solved": len(solved),
        "solve_rate": len(solved) / len(rows) if rows else 0.0,
        "mean_attempts": round(statistics.mean([r["attempts"] for r in solved]), 2) if solved else 0.0,
        "median_latency_ms": round(statistics.median([r["latency_ms"] for r in rows]), 1) if rows else 0.0,
        "rows": rows,
    }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (pct / 100) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def render_report(results: dict) -> str:
    sec = results["security"]
    pipe = results["pipeline"]
    lines = [
        "# MendOps Benchmark Results",
        "",
        f"_Generated by `benchmark/run.py` ({results['backend']} backend)._",
        "",
        "## Security guard",
        "",
        f"- Malicious payloads blocked: **{sec['malicious_blocked']}/{sec['malicious_total']}** ({_percent(sec['block_rate'])})",
        f"- Benign patches allowed: **{sec['benign_allowed']}/{sec['benign_total']}** "
        f"(false-positive rate {_percent(sec['false_positive_rate'])})",
        "",
        "## Pipeline oracle (guard + sandbox)",
        "",
        f"- Seeded bugs: **{pipe['cases']}** across {len(pipe['categories'])} categories "
        f"({', '.join(pipe['categories'])})",
        f"- Oracle-valid cases (buggy fails, fix passes, guard clean): "
        f"**{pipe['oracle_valid']}/{pipe['cases']}** ({_percent(pipe['oracle_rate'])})",
        f"- Validation latency: median **{pipe['median_latency_ms']} ms**, p95 **{pipe['p95_latency_ms']} ms**",
        "",
        "| Bug case | Category | Buggy fails | Guard clean | Fix passes | Latency (ms) |",
        "| --- | --- | :-: | :-: | :-: | --: |",
    ]
    tick = {True: "yes", False: "NO"}
    for row in pipe["rows"]:
        lines.append(
            f"| {row['id']} | {row['category']} | {tick[row['buggy_fails']]} | "
            f"{tick[row['guard_ok']]} | {tick[row['fixed_passes']]} | {row['latency_ms']} |"
        )

    if "llm" in results:
        llm = results["llm"]
        lines += [
            "",
            f"## LLM remediation ({llm['model']})",
            "",
            f"- Bugs auto-fixed end-to-end: **{llm['solved']}/{llm['cases']}** ({_percent(llm['solve_rate'])})",
            f"- Mean attempts per solved bug: **{llm['mean_attempts']}**",
            f"- Median time-to-fix: **{llm['median_latency_ms']} ms**",
        ]
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="MendOps benchmark harness")
    parser.add_argument("--llm", action="store_true", help="also measure live LLM fix rate (needs AI_API_KEY)")
    args = parser.parse_args()

    out_dir = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        results = {
            "backend": os.environ["SANDBOX_BACKEND"],
            "security": evaluate_security(),
            "pipeline": evaluate_pipeline(work_dir),
        }
        if args.llm:
            results["llm"] = evaluate_llm(work_dir)

    report = render_report(results)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (out_dir / "RESULTS.md").write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote {out_dir / 'results.json'} and {out_dir / 'RESULTS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
