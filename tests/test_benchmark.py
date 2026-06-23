import sys
from pathlib import Path

from app.guards import verify_patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "benchmark"))

from corpus import BENIGN_PATCHES, BUG_CASES, MALICIOUS_PATCHES  # noqa: E402


def test_guard_blocks_every_malicious_payload():
    survivors = [name for name, code in MALICIOUS_PATCHES.items() if verify_patch(code).ok]
    assert survivors == [], f"guard let malicious payloads through: {survivors}"


def test_guard_allows_every_benign_patch():
    false_positives = {name: verify_patch(code).errors for name, code in BENIGN_PATCHES.items() if not verify_patch(code).ok}
    assert false_positives == {}, f"guard false-positived benign patches: {false_positives}"


def test_reference_fixes_are_guard_clean():
    dirty = [case.id for case in BUG_CASES if not verify_patch(case.fixed).ok]
    assert dirty == [], f"reference fixes flagged by guard: {dirty}"
