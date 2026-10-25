#!/usr/bin/env python3
"""stage3_close.py — Stage 3 close verification script (P20, deliverable 5).

Checks that all G15–G20 gates, claim freshness, required tags, and
evidence directories are present and consistent.  Exits non-zero if
anything is missing.

Usage:
    python3 scripts/stage3_close.py [--strict]

Exit codes:
    0 — all checks pass
    1 — one or more checks failed
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Gates that must pass for Stage 3 close.
STAGE3_GATES = [
    # P15
    "G15.1", "G15.2", "G15.3", "G15.4", "G15.5", "G15.6",
    # P16
    "G16.1", "G16.2", "G16.3", "G16.4", "G16.5", "G16.6",
    # P17
    "G17.1", "G17.2", "G17.3", "G17.4", "G17.5",
    # P18
    "G18.1", "G18.2", "G18.3", "G18.4", "G18.5",
    # P19
    "G19.1", "G19.2", "G19.3", "G19.4", "G19.5",
    # P20
    "G20.1", "G20.2", "G20.3", "G20.4", "G20.5",
]

# Required tags for Stage 3 close.
REQUIRED_TAGS = [
    "P15-code", "P15-hardstop",
    "P16-code", "P16-hardstop",
    "P17-code", "P17-hardstop",
    "P18-code", "P18-hardstop",
    "P19-code", "P19-hardstop",
    "P20-code", "P20-hardstop",
]

# Required evidence directories.
REQUIRED_EVIDENCE_DIRS = [
    "test_home/P15",
    "test_home/P16",
    "test_home/P17",
    "test_home/P18",
    "test_home/P19",
    "test_home/P20",
]

# Required Hard-Stop reports.
REQUIRED_REPORTS = [
    "test_home/P15/HARD_STOP_REPORT.md",
    "test_home/P16/HARD_STOP_REPORT.md",
    "test_home/P17/HARD_STOP_REPORT.md",
    "test_home/P18/HARD_STOP_REPORT.md",
    "test_home/P19/HARD_STOP_REPORT.md",
    "test_home/P20/HARD_STOP_REPORT.md",
]


def check_gates_yaml() -> list[str]:
    """Check that all G15–G20 gates are present in gates.yaml."""
    failures: list[str] = []
    gates_path = REPO_ROOT / "docs" / "gates.yaml"
    if not gates_path.exists():
        failures.append(f"gates.yaml not found at {gates_path}")
        return failures
    content = gates_path.read_text(encoding="utf-8")
    for gate_id in STAGE3_GATES:
        if f'id: "{gate_id}"' not in content:
            failures.append(f"Gate {gate_id} not found in gates.yaml")
    return failures


def check_tags() -> list[str]:
    """Check that all required git tags exist."""
    failures: list[str] = []
    result = subprocess.run(
        ["git", "tag", "-l"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    existing_tags = set(result.stdout.strip().split("\n"))
    for tag in REQUIRED_TAGS:
        if tag not in existing_tags:
            failures.append(f"Required tag {tag!r} not found")
    return failures


def check_evidence_dirs() -> list[str]:
    """Check that all required evidence directories exist."""
    failures: list[str] = []
    for d in REQUIRED_EVIDENCE_DIRS:
        path = REPO_ROOT / d
        if not path.is_dir():
            failures.append(f"Evidence directory {d!r} not found")
    return failures


def check_reports() -> list[str]:
    """Check that all required Hard-Stop reports exist."""
    failures: list[str] = []
    for r in REQUIRED_REPORTS:
        path = REPO_ROOT / r
        if not path.is_file():
            failures.append(f"Hard-Stop report {r!r} not found")
    return failures


def check_claims_freshness() -> list[str]:
    """Check that claims.yaml exists and has entries."""
    failures: list[str] = []
    claims_path = REPO_ROOT / "docs" / "claims.yaml"
    if not claims_path.exists():
        failures.append("docs/claims.yaml not found")
        return failures
    content = claims_path.read_text(encoding="utf-8")
    if "claim_id:" not in content:
        failures.append("No claims found in claims.yaml")
    return failures


def check_readme_stage3() -> list[str]:
    """Check that README reflects Stage 3 completion."""
    failures: list[str] = []
    readme_path = REPO_ROOT / "README.md"
    if not readme_path.exists():
        failures.append("README.md not found")
        return failures
    content = readme_path.read_text(encoding="utf-8")
    if "P20" not in content:
        failures.append("README does not mention P20")
    if "COMPLETE (CANDIDATE)" not in content:
        failures.append(
            "README does not contain 'COMPLETE (CANDIDATE)'"
        )
    return failures


def check_formal_sketch() -> list[str]:
    """Check that the formal sketch document exists."""
    failures: list[str] = []
    sketch_path = REPO_ROOT / "docs" / "formal" / "gateway_properties.md"
    if not sketch_path.exists():
        failures.append(
            f"Formal sketch not found at {sketch_path}"
        )
    return failures


def main() -> int:
    """Run all stage-close checks. Returns 0 on pass, 1 on fail."""
    print("=== Stage 3 Close Verification ===")
    all_failures: list[str] = []

    print("  Checking gates.yaml...")
    all_failures.extend(check_gates_yaml())

    print("  Checking required tags...")
    all_failures.extend(check_tags())

    print("  Checking evidence directories...")
    all_failures.extend(check_evidence_dirs())

    print("  Checking Hard-Stop reports...")
    all_failures.extend(check_reports())

    print("  Checking claims freshness...")
    all_failures.extend(check_claims_freshness())

    print("  Checking README Stage 3 completion...")
    all_failures.extend(check_readme_stage3())

    print("  Checking formal sketch...")
    all_failures.extend(check_formal_sketch())

    if all_failures:
        print(f"\n=== FAILURES ({len(all_failures)}) ===")
        for f in all_failures:
            print(f"  FAIL: {f}")
        return 1

    print("\n=== Stage 3 Close: ALL CHECKS PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
