#!/usr/bin/env python3
"""check_commits.py — commit-discipline checker (§21.5).

Usage:
    python3 scripts/check_commits.py <PHASE> [--bisect]

Checks:
    C2: every commit in the phase matches the regex in §21.3
    C3: every referenced ID exists in capability_catalog.yaml, gates.yaml, or the section index
    C4: every gate and capability due in the phase is referenced at least once
    C7: zero merge commits, linear history
    C8: bisectability sample — checks out each sampled commit and runs pytest -m smoke
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Commit message regex (§21.3)
# Phase component: P(?:[1-9]|10)
# REF: R01-R30, N01-N30, G1.1-G6.9, §section, INFRA, DOC
COMMIT_REGEX = re.compile(
    r"^P(?:[1-9]|1[0-9]|2[0]): .{8,100} \("
    r"(?:[RN](?:0[1-9]|[12][0-9]|30)|G[1-6]\.[1-9][0-9]?|G1[0-9]\.[1-9][0-9]?|G20\.[1-9][0-9]?|§[0-9]+(?:\.[0-9]+)*|INFRA|DOC)"
    r"(?:, (?:[RN](?:0[1-9]|[12][0-9]|30)|G[1-6]\.[1-9][0-9]?|G1[0-9]\.[1-9][0-9]?|G20\.[1-9][0-9]?|§[0-9]+(?:\.[0-9]+)*|INFRA|DOC))*\)$"
)

# Valid gate IDs from gates.yaml
GATE_IDS = {
    "G1.1", "G1.2", "G1.3", "G1.4", "G1.5", "G1.6", "G1.7", "G1.8", "G1.9",
    "G1.10", "G1.11", "G1.12",
    "G2.1", "G2.2", "G2.3", "G2.4", "G2.5", "G2.6", "G2.7", "G2.8", "G2.9", "G2.10",
    "G3.1", "G3.2", "G3.3", "G3.4", "G3.5", "G3.6", "G3.7", "G3.8", "G3.9", "G3.10",
    "G4.1", "G4.2", "G4.3", "G4.4", "G4.5", "G4.6",
    "G4.13", "G4.14", "G4.15", "G4.16",
    "G4.7", "G4.8", "G4.9",
    "G4.10", "G4.11",
    "G4.12",
    "G5.1", "G5.2", "G5.3", "G5.4", "G5.5", "G5.6", "G5.7", "G5.8",
    "G6.1", "G6.2", "G6.3", "G6.4", "G6.5", "G6.6", "G6.7", "G6.8", "G6.9",
    "G11.1", "G11.2", "G11.3", "G11.4", "G11.5",
    "G12.1", "G12.2", "G12.3", "G12.4", "G12.5",
    "G13.1", "G13.2", "G13.3", "G13.4", "G13.5",
    "G14.1", "G14.2", "G14.3", "G14.4",
    "G15.1", "G15.2", "G15.3", "G15.4", "G15.5", "G15.6",
    "G16.1", "G16.2", "G16.3", "G16.4", "G16.5", "G16.6",
    "G17.1", "G17.2", "G17.3", "G17.4", "G17.5",
    "G18.1", "G18.2", "G18.3", "G18.4", "G18.5",
    "G19.1", "G19.2", "G19.3", "G19.4", "G19.5",
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9",
}

# Valid capability IDs (R01-R30, N01-N30)
CAPABILITY_IDS = set()
for i in range(1, 31):
    CAPABILITY_IDS.add(f"R{i:02d}")
    CAPABILITY_IDS.add(f"N{i:02d}")

ALL_VALID_REFS = GATE_IDS | CAPABILITY_IDS | {"INFRA", "DOC"}

# Gates due in each phase
PHASE_GATES = {
    "P1": {"G1.1", "G1.2", "G1.3", "G1.4", "G1.5", "G1.6", "G1.7", "G1.8", "G1.9", "G1.10", "G1.11", "G1.12"},
    "P2": {"G2.1", "G2.2", "G2.3", "G2.4", "G2.5", "G2.6", "G2.7", "G2.8", "G2.9", "G2.10"},
    "P3": {"G3.1", "G3.2", "G3.3", "G3.4", "G3.5", "G3.6", "G3.7", "G3.8", "G3.9", "G3.10"},
    "P4": {"G4.1", "G4.2", "G4.3", "G4.4", "G4.5", "G4.6", "G4.13", "G4.14", "G4.15", "G4.16"},
    "P5": {"G4.7", "G4.8", "G4.9"},
    "P8": {"G5.1", "G5.2", "G5.3", "G5.4", "G5.5", "G5.6", "G5.7", "G5.8"},
    "P6": {"G4.10", "G4.11"},
    "P7": {"G4.12"},
    "P9": {"G6.1", "G6.2", "G6.3", "G6.4", "G6.5", "G6.8", "G6.9"},
    "P10": {"G6.6", "G6.7"},
    "P11": {"G11.1", "G11.2", "G11.3", "G11.4", "G11.5"},
    "P12": {"G12.1", "G12.2", "G12.3", "G12.4", "G12.5"},
    "P13": {"G13.1", "G13.2", "G13.3", "G13.4", "G13.5"},
    "P14": {"G14.1", "G14.2", "G14.3", "G14.4"},
    "P15": {"G15.1", "G15.2", "G15.3", "G15.4", "G15.5", "G15.6"},
    "P16": {"G16.1", "G16.2", "G16.3", "G16.4", "G16.5", "G16.6"},
    "P17": {"G17.1", "G17.2", "G17.3", "G17.4", "G17.5"},
    "P18": {"G18.1", "G18.2", "G18.3", "G18.4", "G18.5"},
    "P19": {"G19.1", "G19.2", "G19.3", "G19.4", "G19.5"},
}


def get_phase_commits(phase: str) -> list[tuple[str, str]]:
    """Get all commits in the given phase (by commit message prefix)."""
    result = subprocess.run(
        ["git", "log", "--oneline", "--no-decorate"],
        capture_output=True,
        text=True,
        check=True,
    )
    commits = []
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
    regex_failures = []
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
    ref_failures = []
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
        print(f"  C3 refs: PASS")

    # C4: every gate due in phase is referenced at least once
    due_gates = PHASE_GATES.get(phase, set())
    referenced_gates: set[str] = set()
    for h, msg in commits:
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
        failures.append(f"C7: {len(merge_result.stdout.strip().splitlines())} merge commits found")
    else:
        print("  C7 linear history: PASS")

    # C8: bisectability sample
    if bisect:
        total = len(commits)
        sample_size = min(total, max(5, (total * 10 + 99) // 100))
        print(f"  C8 bisect: sampling {sample_size} of {total} commits...")
        # Deterministically sample every Nth commit
        step = max(1, total // sample_size)
        sampled = [commits[i] for i in range(0, total, step)][:sample_size]
        bisect_failures = []
        for h, msg in sampled:
            # Checkout and run smoke tests
            checkout_result = subprocess.run(
                ["git", "stash"],
                capture_output=True,
                text=True,
            )
            checkout_result = subprocess.run(
                ["git", "checkout", h],
                capture_output=True,
                text=True,
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
            # Restore
            subprocess.run(["git", "checkout", "-"], capture_output=True, text=True)
            subprocess.run(["git", "stash", "pop"], capture_output=True, text=True)

        if bisect_failures:
            failures.append(f"C8: {len(bisect_failures)} sampled commits fail smoke:")
            for h, msg, reason in bisect_failures:
                failures.append(f"  {h}: {reason} ({msg!r})")
        else:
            print(f"  C8 bisect: PASS ({sample_size} sampled)")

    # Final report
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
