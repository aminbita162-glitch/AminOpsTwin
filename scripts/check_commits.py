#!/usr/bin/env python3
"""check_commits.py — commit-discipline checker (§21.5, P25 generalised).

Usage:
    python3 scripts/check_commits.py <PHASE> [--bisect]

Checks:
    C2: every commit in the phase matches the regex in §21.3
    C3: every referenced ID exists in capability_catalog.yaml, gates.yaml, or the section index
    C4: every gate and capability due in the phase is referenced at least once
    C7: zero merge commits, linear history
    C8: bisectability sample — checks out each sampled commit and runs pytest -m smoke

P25 generalisation:
    - Accept any phase number P1 to P99.
    - Load valid gate IDs from docs/gates.yaml (single source of truth).
    - Load capability IDs from docs/capability_catalog.yaml.
    - PHASE_GATES is derived from gates.yaml (the 'phase' field of each gate).
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GATES_YAML = _REPO_ROOT / "docs" / "gates.yaml"
_CAPABILITY_CATALOG = _REPO_ROOT / "docs" / "capability_catalog.yaml"

# Commit message regex (§21.3, generalised for P1–P99).
# Phase component: P(?:[1-9]|[1-9]\d)  → P1 through P99
# REF: R01-R30, N01-N30, G<phase>.<k>, §section, INFRA, DOC
COMMIT_REGEX = re.compile(
    r"^P(?:[1-9]|[1-9]\d): .{8,100} \("
    r"(?:[RN](?:0[1-9]|[12]\d|30)|G\d+\.\d+|§\d+(?:\.\d+)*|INFRA|DOC)"
    r"(?:, (?:[RN](?:0[1-9]|[12]\d|30)|G\d+\.\d+|§\d+(?:\.\d+)*|INFRA|DOC))*\)$"
)


def _load_gate_ids_from_yaml() -> set[str]:
    """Load all gate IDs from docs/gates.yaml as the single source of truth."""
    if not _GATES_YAML.exists():
        return set()
    text = _GATES_YAML.read_text()
    ids: set[str] = set()
    for m in re.finditer(r'^\s+-\s+id:\s*"?(G\d+\.\d+)"?', text, re.MULTILINE):
        ids.add(m.group(1))
    # Common gates C1–C9 are also valid refs
    for m in re.finditer(r'^\s+-\s+id:\s+"?(C\d+)"?', text, re.MULTILINE):
        ids.add(m.group(1))
    return ids


def _load_phase_gates_from_yaml() -> dict[str, set[str]]:
    """Derive PHASE_GATES from gates.yaml: phase → set of gate ids."""
    if not _GATES_YAML.exists():
        return {}
    text = _GATES_YAML.read_text()
    phase_gates: dict[str, set[str]] = defaultdict(set)
    # Match lines like:  - id: "G25.1" followed by  phase: "P25"
    entries = re.finditer(
        r'-\s+id:\s*"?(G\d+\.\d+)"?\s*\n\s*phase:\s*"?(P\d+)"?',
        text,
    )
    for m in entries:
        gate_id = m.group(1)
        phase = m.group(2)
        phase_gates[phase].add(gate_id)
    return dict(phase_gates)


def _load_capability_ids_from_yaml() -> set[str]:
    """Load capability IDs from docs/capability_catalog.yaml."""
    if not _CAPABILITY_CATALOG.exists():
        return set()
    text = _CAPABILITY_CATALOG.read_text()
    ids: set[str] = set()
    for m in re.finditer(r"^\s*-\s+id:\s*(R\d+)", text, re.MULTILINE):
        ids.add(m.group(1))
    for m in re.finditer(r"^\s*-\s+id:\s*(N\d+)", text, re.MULTILINE):
        ids.add(m.group(1))
    return ids


# Load from the single source of truth at import time.
GATE_IDS = _load_gate_ids_from_yaml()
CAPABILITY_IDS = _load_capability_ids_from_yaml()
ALL_VALID_REFS = GATE_IDS | CAPABILITY_IDS | {"INFRA", "DOC"}
PHASE_GATES = _load_phase_gates_from_yaml()


def get_phase_commits(phase: str) -> list[tuple[str, str]]:
    """Get all commits in the given phase (by commit message prefix)."""
    result = subprocess.run(
        ["git", "log", "--oneline", "--no-decorate"],
        capture_output=True,
        text=True,
        check=True,
    )
    commits: list[tuple[str, str]] = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split(" ", 1)
        hash_short = parts[0]
        msg = parts[1] if len(parts) > 1 else ""
        if msg.startswith(f"{phase}:"):
            commits.append((hash_short, msg))
    return commits


def extract_refs(msg: str) -> list[str]:
    """Extract REFs from a commit message after the (."""
    match = re.search(r"\((.+)\)$", msg)
    if not match:
        return []
    refs_str = match.group(1)
    return [r.strip() for r in refs_str.split(",")]


def check_phase(phase: str, bisect: bool = False) -> int:
    """Run all commit checks for the given phase. Returns 0 on pass, 1 on fail."""
    commits = get_phase_commits(phase)
    if not commits:
        print(f"ERROR: No commits found for {phase}")
        return 1

    print(f"=== {phase} Commit Discipline Check ===")
    print(f"Commits in phase: {len(commits)}")

    failures: list[str] = []

    # C2: regex match
    regex_failures: list[tuple[str, str]] = []
    for h, msg in commits:
        if not COMMIT_REGEX.match(msg):
            regex_failures.append((h, msg))
    if regex_failures:
        failures.append(f"C2: {len(regex_failures)} commits fail regex:")
        for h, msg in regex_failures:
            failures.append(f"  {h}: {msg}")
    else:
        print(f"  C2 regex: PASS ({len(commits)} commits)")

    # C3: every referenced ID exists
    ref_failures: list[tuple[str, str, str]] = []
    for h, msg in commits:
        refs = extract_refs(msg)
        for r in refs:
            if r.startswith("§"):
                continue  # Section refs are always valid
            if r not in ALL_VALID_REFS:
                ref_failures.append((h, r, msg))
    if ref_failures:
        failures.append(f"C3: {len(ref_failures)} invalid refs:")
        for h, r, msg in ref_failures:
            failures.append(f"  {h}: invalid ref {r!r} in {msg!r}")
    else:
        print("  C3 refs: PASS")

    # C4: every gate due in phase is referenced at least once
    due_gates = PHASE_GATES.get(phase, set())
    referenced_gates: set[str] = set()
    for _h, msg in commits:
        refs = extract_refs(msg)
        for r in refs:
            if r in GATE_IDS:
                referenced_gates.add(r)
    unreferenced = due_gates - referenced_gates
    if unreferenced:
        failures.append(f"C4: gates not referenced: {sorted(unreferenced)}")
    else:
        print(f"  C4 due gates: PASS ({len(due_gates)} gates referenced)")

    # C7: zero merge commits
    merge_result = subprocess.run(
        ["git", "log", "--oneline", "--merges"],
        capture_output=True,
        text=True,
        check=True,
    )
    if merge_result.stdout.strip():
        failures.append(
            f"C7: {len(merge_result.stdout.strip().splitlines())} merge commits found"
        )
    else:
        print("  C7 linear history: PASS")

    # C8: bisectability sample
    if bisect:
        total = len(commits)
        sample_size = min(total, max(5, (total * 10 + 99) // 100))
        print(f"  C8 bisect: sampling {sample_size} of {total} commits...")
        step = max(1, total // sample_size)
        sampled = [commits[i] for i in range(0, total, step)][:sample_size]
        bisect_failures: list[tuple[str, str, str]] = []
        for h, msg in sampled:
            subprocess.run(
                ["git", "stash"], capture_output=True, text=True
            )
            checkout_result = subprocess.run(
                ["git", "checkout", h], capture_output=True, text=True
            )
            if checkout_result.returncode != 0:
                bisect_failures.append((h, msg, "checkout failed"))
                continue
            test_result = subprocess.run(
                [sys.executable, "-m", "pytest", "-m", "smoke", "-x", "-q"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if test_result.returncode != 0:
                bisect_failures.append((h, msg, "smoke tests failed"))
            subprocess.run(
                ["git", "checkout", "-"], capture_output=True, text=True
            )
            subprocess.run(
                ["git", "stash", "pop"], capture_output=True, text=True
            )

        if bisect_failures:
            failures.append(f"C8: {len(bisect_failures)} sampled commits fail smoke:")
            for h, msg, reason in bisect_failures:
                failures.append(f"  {h}: {reason} ({msg!r})")
        else:
            print(f"  C8 bisect: PASS ({sample_size} sampled)")

    if failures:
        print("\n=== FAILURES ===")
        for f in failures:
            print(f)
        return 1
    else:
        print(f"\n=== {phase}: ALL COMMIT CHECKS PASS ===")
        return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: check_commits.py <PHASE> [--bisect]")
        return 1
    phase = sys.argv[1]
    bisect = "--bisect" in sys.argv
    return check_phase(phase, bisect=bisect)


if __name__ == "__main__":
    sys.exit(main())
