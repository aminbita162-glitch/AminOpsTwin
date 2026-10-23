#!/usr/bin/env bash
# verify_manifest.sh — binding manifest check (C1, §8).
#
# Checks that the binding files match the signed manifest.
# In P1, the manifest is proposed by the agent and signed by the owner
# at the Hard Stop. If no manifest exists, the check passes (proposed).

set -euo pipefail

MANIFEST="docs/binding_manifest.sha256"

if [ -f "$MANIFEST" ]; then
    if sha256sum -c "$MANIFEST" 2>/dev/null; then
        echo "PASS: binding manifest verified"
        exit 0
    else
        echo "FAIL: binding manifest mismatch"
        exit 1
    fi
else
    echo "SKIP: no binding manifest (P1 proposes, owner signs)"
    exit 0
fi
