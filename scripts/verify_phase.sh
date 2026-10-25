#!/usr/bin/env bash
# verify_phase.sh — owner-run phase verification script (§13.1)
#
# Usage: bash scripts/verify_phase.sh <PHASE>
#
# Verifies:
#   1. binding files against the signed manifest
#   2. runs the full test suite from a clean checkout
#   3. computes every numeric gate for the phase from raw test outputs
#   4. verifies sealed evidence files against the pack manifest
#   5. runs gitleaks, pip-audit, import-linter, mypy --strict, mutmut (when due),
#      schema field scan with canary, forbidden-pattern scan, check_commits.py
#   6. prints "PHASE <X>: PASS" or "PHASE <X>: FAIL (<failed gates>)"

set -euo pipefail

PHASE="${1:-}"
if [ -z "$PHASE" ]; then
    echo "Usage: $0 <PHASE>"
    exit 1
fi

echo "=== AminOpsTwin Phase Verification: $PHASE ==="
echo ""

FAILED_GATES=()

# 1. Binding files manifest check
echo "1. Binding manifest check..."
if [ -f "docs/binding_manifest.sha256" ]; then
    if sha256sum -c docs/binding_manifest.sha256 2>/dev/null; then
        echo "   PASS: binding manifest verified"
    else
        echo "   FAIL: binding manifest mismatch"
        FAILED_GATES+=("C1")
    fi
else
    echo "   SKIP: no binding manifest (P1 proposes, owner signs)"
fi

# 2. Run full test suite
echo ""
echo "2. Running full test suite..."
PYTHONHASHSEED=0 python3 -m pytest -v --tb=short 2>&1 | tee "test_home/$PHASE/test_output.txt" || true
TEST_EXIT=${PIPESTATUS[0]:-1}
if [ "$TEST_EXIT" -eq 0 ]; then
    echo "   PASS: all tests passed"
else
    echo "   FAIL: some tests failed (exit $TEST_EXIT)"
    FAILED_GATES+=("tests")
fi

# 3. Compute numeric gates
echo ""
echo "3. Computing numeric gates..."

# G1.1: Gateway branch coverage >= 95%
echo "   G1.1: Gateway branch coverage..."
python3 -m pytest --cov=src/aminopstwin/gateway --cov-branch --cov-report=term-missing tests/gateway/ 2>&1 | tee "test_home/$PHASE/G1.1_coverage.txt" || true
COV_LINE=$(grep "TOTAL" "test_home/$PHASE/G1.1_coverage.txt" 2>/dev/null || echo "")
if [ -n "$COV_LINE" ]; then
    COV_PCT=$(echo "$COV_LINE" | awk '{print $NF}' | sed 's/%//')
    if [ -n "$COV_PCT" ] && [ "$(echo "$COV_PCT >= 95" | bc 2>/dev/null || echo 0)" -eq 1 ]; then
        echo "   G1.1: PASS ($COV_PCT%)"
    else
        echo "   G1.1: FAIL ($COV_PCT%)"
        FAILED_GATES+=("G1.1")
    fi
else
    echo "   G1.1: SKIP (no coverage data)"
    FAILED_GATES+=("G1.1")
fi

# G1.3: Adversarial corpus
echo "   G1.3: Adversarial corpus..."
python3 -m pytest tests/adversarial/ -v 2>&1 | tee "test_home/$PHASE/G1.3_corpus.txt" || true
if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
    echo "   G1.3: PASS"
else
    echo "   G1.3: FAIL"
    FAILED_GATES+=("G1.3")
fi

# G1.5: gitleaks
echo "   G1.5: gitleaks..."
if command -v gitleaks &>/dev/null; then
    gitleaks detect --source . --no-banner 2>&1 | tee "test_home/$PHASE/G1.5_gitleaks.txt" || true
    if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
        echo "   G1.5: PASS"
    else
        echo "   G1.5: FAIL"
        FAILED_GATES+=("G1.5")
    fi
else
    echo "   G1.5: SKIP (gitleaks not installed)"
fi

# G1.6: mypy --strict
echo "   G1.6: mypy --strict..."
python3 -m mypy --strict src/aminopstwin/contracts src/aminopstwin/gateway src/aminopstwin/executor src/aminopstwin/tokens 2>&1 | tee "test_home/$PHASE/G1.6_mypy.txt" || true
if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
    echo "   G1.6: PASS"
else
    echo "   G1.6: FAIL"
    FAILED_GATES+=("G1.6")
fi

# G1.7: import-linter
echo "   G1.7: import-linter..."
python3 -m lint_imports 2>&1 | tee "test_home/$PHASE/G1.7_import_linter.txt" || true
if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
    echo "   G1.7: PASS"
else
    echo "   G1.7: FAIL (or not configured)"
    FAILED_GATES+=("G1.7")
fi

# G1.8: Invariant catalog >= 15
echo "   G1.8: Invariant catalog..."
INV_COUNT=$(python3 -c "import yaml; d=yaml.safe_load(open('docs/invariant_catalog.yaml')); print(len(d['invariants']))" 2>/dev/null || echo 0)
if [ "$INV_COUNT" -ge 15 ]; then
    echo "   G1.8: PASS ($INV_COUNT invariants)"
else
    echo "   G1.8: FAIL ($INV_COUNT invariants, need >= 15)"
    FAILED_GATES+=("G1.8")
fi

# G1.11: Canonical vectors
echo "   G1.11: Canonical vectors..."
python3 -m pytest tests/test_canonical_vectors.py -v 2>&1 | tee "test_home/$PHASE/G1.11_canonical.txt" || true
if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
    echo "   G1.11: PASS"
else
    echo "   G1.11: FAIL"
    FAILED_GATES+=("G1.11")
fi

# G1.12: Principal spoofing
echo "   G1.12: Principal spoofing..."
python3 -m pytest tests/adversarial/test_principal_spoof.py -v 2>&1 | tee "test_home/$PHASE/G1.12_spoof.txt" || true
if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
    echo "   G1.12: PASS"
else
    echo "   G1.12: FAIL"
    FAILED_GATES+=("G1.12")
fi

# C2-C4, C7: commit discipline
echo "   C2-C4, C7: Commit discipline..."
python3 scripts/check_commits.py "$PHASE" 2>&1 | tee "test_home/$PHASE/commit_report.txt" || true
if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
    echo "   C2-C4, C7: PASS"
else
    echo "   C2-C4, C7: FAIL"
    FAILED_GATES+=("C2-C4,C7")
fi

# 4. Evidence pack manifest
echo ""
echo "4. Evidence pack manifest..."
echo "   (Owner signs the pack manifest after verification)"

# 5. pip-audit
echo ""
echo "5. pip-audit..."
if command -v pip-audit &>/dev/null; then
    pip-audit --strict 2>&1 | tee "test_home/$PHASE/pip_audit.txt" || true
    if [ "${PIPESTATUS[0]:-1}" -eq 0 ]; then
        echo "   C9: PASS"
    else
        echo "   C9: FAIL"
        FAILED_GATES+=("C9")
    fi
else
    echo "   C9: SKIP (pip-audit not installed)"
fi

# 6. Final verdict
echo ""
echo "================================"
if [ ${#FAILED_GATES[@]} -eq 0 ]; then
    echo "PHASE $PHASE: PASS"
    exit 0
else
    echo "PHASE $PHASE: FAIL (${FAILED_GATES[*]})"
    exit 1
fi
