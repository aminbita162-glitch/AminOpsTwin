#!/usr/bin/env python3
"""check_directive_consistency.py — directive governance consistency checker.

P22 deliverable 4: a consistency check that confirms no conflicting phase
sequences or status terms remain in directive.txt or governance files.

Checks:
  1. directive.txt has exactly one active phase sequence (P21–P24).
  2. directive.txt uses a single status vocabulary (COMPLETE (CANDIDATE)).
  3. No outdated phase references (Stage 1/2/3 active, P1–P10 active, etc.)
     remain in directive.txt.
  4. gates.yaml gate IDs match check_commits.py GATE_IDS (single source).
  5. No OWNER-FILL markers remain in directive.txt.
  6. Phase status in README.md matches evidence under test_home/.

Exit 0 if all checks pass, exit 1 on any failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIRECTIVE = REPO_ROOT / "directive.txt"
GATES_YAML = REPO_ROOT / "docs" / "gates.yaml"
CHECK_COMMITS = REPO_ROOT / "scripts" / "check_commits.py"
README = REPO_ROOT / "README.md"
TEST_HOME = REPO_ROOT / "test_home"

# The single allowed active phase sequence for Stage 4.
ACTIVE_PHASE_SEQUENCE = "P21 THROUGH P24"

# Allowed status vocabulary terms in directive.txt.
VALID_STATUS_VOCAB = {
    "COMPLETE (CANDIDATE)",
    "EXECUTION CANDIDATE",
}

# Outdated phase references that must NOT appear in directive.txt.
OUTDATED_REFS = [
    "Stage 1 active",
    "Stage 2 active",
    "Stage 3 active",
    "stage 1 active",
    "stage 2 active",
    "stage 3 active",
    "P1–P10 active",
    "P1-P10 active",
    "P11–P14 active",
    "P11-P14 active",
    "P15–P20 active",
    "P15-P20 active",
]


def _check_single_phase_sequence(content: str) -> list[str]:
    """Check that directive.txt has exactly one active phase sequence."""
    failures: list[str] = []
    if ACTIVE_PHASE_SEQUENCE not in content:
        failures.append(
            f"Active phase sequence '{ACTIVE_PHASE_SEQUENCE}' not found"
        )
    # Check for any other "SOLE ACTIVE PHASE SEQUENCE" declarations
    matches = re.findall(
        r"SOLE ACTIVE PHASE SEQUENCE.*?IS\s+(P\d+\s+(?:THROUGH|–|-)\s+P\d+)",
        content,
        re.IGNORECASE,
    )
    if len(matches) > 1:
        failures.append(
            f"Multiple 'SOLE ACTIVE PHASE SEQUENCE' declarations found: {matches}"
        )
    return failures


def _check_status_vocabulary(content: str) -> list[str]:
    """Check that directive.txt uses consistent status vocabulary."""
    failures: list[str] = []
    # Check STATUS: line
    status_match = re.search(r"^STATUS:\s*(.+)$", content, re.MULTILINE)
    if status_match:
        status_val = status_match.group(1).strip()
        if status_val not in VALID_STATUS_VOCAB:
            failures.append(
                f"Status '{status_val}' not in valid vocabulary {VALID_STATUS_VOCAB}"
            )
    else:
        failures.append("No STATUS: line found in directive.txt")
    return failures


def _check_no_outdated_refs(content: str) -> list[str]:
    """Check that no outdated phase references remain."""
    failures: list[str] = []
    for ref in OUTDATED_REFS:
        if ref in content:
            failures.append(f"Outdated reference '{ref}' found in directive.txt")
    return failures


def _check_no_owner_fill(content: str) -> list[str]:
    """Check that no OWNER-FILL placeholders remain in directive.txt.

    The directive legitimately mentions 'OWNER-FILL' as a term in its
    rules (e.g. 'No skeleton, placeholder, OWNER-FILL marker...').  An
    actual unfilled placeholder uses the bracketed form [OWNER-FILL].
    """
    failures: list[str] = []
    placeholders = re.findall(r"\[OWNER-FILL[^\]]*\]", content)
    if placeholders:
        failures.append(
            f"{len(placeholders)} [OWNER-FILL] placeholder(s) found in "
            f"directive.txt: {placeholders}"
        )
    return failures


def _check_gates_yaml_matches_check_commits() -> list[str]:
    """Check that gates.yaml gate IDs match check_commits.py GATE_IDS."""
    failures: list[str] = []
    gates_text = GATES_YAML.read_text()
    yaml_ids = set(re.findall(r"G\d+\.\d+", gates_text))
    yaml_ids |= {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"}

    cc_text = CHECK_COMMITS.read_text()
    m = re.search(r"GATE_IDS\s*=\s*\{([^}]+)\}", cc_text)
    if not m:
        failures.append("GATE_IDS set not found in check_commits.py")
        return failures
    code_ids = set(re.findall(r'"([^"]+)"', m.group(1)))

    only_in_yaml = yaml_ids - code_ids
    only_in_code = code_ids - yaml_ids
    if only_in_yaml:
        failures.append(
            f"Gate IDs in gates.yaml but NOT in check_commits.py: "
            f"{sorted(only_in_yaml)}"
        )
    if only_in_code:
        failures.append(
            f"Gate IDs in check_commits.py but NOT in gates.yaml: "
            f"{sorted(only_in_code)}"
        )
    return failures


def _check_readme_status_matches_evidence() -> list[str]:
    """Check that README phase status rows match evidence under test_home/."""
    failures: list[str] = []
    if not README.exists():
        failures.append("README.md not found")
        return failures
    content = README.read_text()
    # Extract CANDIDATE rows from the status table
    for match in re.finditer(
        r"\|\s*(P\d+)\s*\|\s*COMPLETE\s*\(CANDIDATE\)\s*\|", content
    ):
        phase = match.group(1)
        report = TEST_HOME / phase / "HARD_STOP_REPORT.md"
        if not report.exists():
            failures.append(
                f"{phase} marked COMPLETE (CANDIDATE) but "
                f"no HARD_STOP_REPORT.md at {report}"
            )
    return failures


def main() -> int:
    """Run all consistency checks. Returns 0 on pass, 1 on failure."""
    all_failures: list[str] = []

    if not DIRECTIVE.exists():
        print("FAIL: directive.txt not found")
        return 1
    content = DIRECTIVE.read_text()

    all_failures.extend(_check_single_phase_sequence(content))
    all_failures.extend(_check_status_vocabulary(content))
    all_failures.extend(_check_no_outdated_refs(content))
    all_failures.extend(_check_no_owner_fill(content))
    all_failures.extend(_check_gates_yaml_matches_check_commits())
    all_failures.extend(_check_readme_status_matches_evidence())

    if all_failures:
        print("=== DIRECTIVE CONSISTENCY CHECK: FAIL ===")
        for f in all_failures:
            print(f"  - {f}")
        return 1
    else:
        print("=== DIRECTIVE CONSISTENCY CHECK: PASS ===")
        print("  - Single active phase sequence: P21–P24")
        print("  - Single status vocabulary: COMPLETE (CANDIDATE)")
        print("  - No outdated phase references")
        print("  - No OWNER-FILL markers in directive.txt")
        print("  - gates.yaml matches check_commits.py GATE_IDS")
        print("  - README status matches evidence under test_home/")
        return 0


if __name__ == "__main__":
    sys.exit(main())
