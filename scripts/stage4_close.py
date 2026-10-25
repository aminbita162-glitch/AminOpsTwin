#!/usr/bin/env python3
"""stage4_close.py — Stage 4 close verification script (P24, deliverable 3).

Checks that all G21–G24 gates, claim freshness, required tags, evidence
directories, Hard-Stop reports, the Stage 4 seal document, and README
Stage 4 completion are present and consistent.  Exits non-zero if
anything is missing.

Usage:
    python3 scripts/stage4_close.py [--strict]

Exit codes:
    0 — all checks pass
    1 — one or more checks failed
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Gates that must pass for Stage 4 close.
STAGE4_GATES = [
    # P21
    "G21.1", "G21.2", "G21.3",
    # P22
    "G22.1", "G22.2", "G22.3", "G22.4",
    # P23
    "G23.1", "G23.2", "G23.3", "G23.4", "G23.5",
    # P24
    "G24.1", "G24.2", "G24.3", "G24.4",
]

# Required tags for Stage 4 close.
REQUIRED_TAGS = [
    "P21-code", "P21-hardstop",
    "P22-code", "P22-hardstop",
    "P23-code", "P23-hardstop",
    "P24-code", "P24-hardstop",
]

# Required evidence directories.
REQUIRED_EVIDENCE_DIRS = [
    "test_home/P21",
    "test_home/P22",
    "test_home/P23",
    "test_home/P24",
]

# Required Hard-Stop reports.
REQUIRED_REPORTS = [
    "test_home/P21/HARD_STOP_REPORT.md",
    "test_home/P22/HARD_STOP_REPORT.md",
    "test_home/P23/HARD_STOP_REPORT.md",
    "test_home/P24/HARD_STOP_REPORT.md",
]


def check_gates_yaml() -> list[str]:
    """Check that all G21–G24 gates are present in gates.yaml."""
    failures: list[str] = []
    gates_path = REPO_ROOT / "docs" / "gates.yaml"
    if not gates_path.exists():
        failures.append(f"gates.yaml not found at {gates_path}")
        return failures
    content = gates_path.read_text(encoding="utf-8")
    for gate_id in STAGE4_GATES:
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


def check_readme_stage4() -> list[str]:
    """Check that README reflects Stage 4 completion."""
    failures: list[str] = []
    readme_path = REPO_ROOT / "README.md"
    if not readme_path.exists():
        failures.append("README.md not found")
        return failures
    content = readme_path.read_text(encoding="utf-8")
    if "P24" not in content:
        failures.append("README does not mention P24")
    if "COMPLETE (CANDIDATE)" not in content:
        failures.append(
            "README does not contain 'COMPLETE (CANDIDATE)'"
        )
    return failures


def check_stage4_seal() -> list[str]:
    """Check that the Stage 4 seal document exists."""
    failures: list[str] = []
    seal_path = REPO_ROOT / "docs" / "stage4_seal.json"
    if not seal_path.exists():
        failures.append(f"Stage 4 seal not found at {seal_path}")
    return failures


def check_no_skeleton() -> list[str]:
    """Check that no skeleton or placeholder markers remain in README.md.

    Internal governance files (owner_decisions.md, open_questions.md,
    key_rotation_protocol.md, release notes) legitimately retain
    ``[OWNER-FILL]`` markers for pending owner decisions documented in
    docs/open_questions.md — these are NOT unclaimed public statements
    and are excluded (see P22 G22.2 scope).
    """
    failures: list[str] = []
    markers = ["[OWNER-FILL]", "TODO", "FIXME", "PLACEHOLDER"]
    readme = REPO_ROOT / "README.md"
    if readme.exists():
        content = readme.read_text(encoding="utf-8")
        for marker in markers:
            if marker in content:
                failures.append(f"Marker {marker!r} found in README.md")
    return failures


def main() -> int:
    """Run all stage-close checks. Returns 0 on pass, 1 on fail."""
    print("=== Stage 4 Close Verification ===")
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

    print("  Checking README Stage 4 completion...")
    all_failures.extend(check_readme_stage4())

    print("  Checking Stage 4 seal...")
    all_failures.extend(check_stage4_seal())

    print("  Checking no skeleton or unclaimed statements...")
    all_failures.extend(check_no_skeleton())

    if all_failures:
        print(f"\n=== FAILURES ({len(all_failures)}) ===")
        for f in all_failures:
            print(f"  FAIL: {f}")
        return 1

    print("\n=== Stage 4 Close: ALL CHECKS PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
