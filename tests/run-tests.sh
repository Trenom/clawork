#!/usr/bin/env bash
# Run all Phase 1 skill tests.
# Exit code: 0 if all pass, 1 if any fail.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FAILURES=0

for test_file in "$SCRIPT_DIR"/test_router.py "$SCRIPT_DIR"/test_soul.py "$SCRIPT_DIR"/test_sessions.py; do
    echo ""
    echo "============================================"
    echo "Running: $(basename "$test_file")"
    echo "============================================"
    if python3 "$test_file"; then
        echo "  -> OK"
    else
        echo "  -> FAILED"
        FAILURES=$((FAILURES + 1))
    fi
done

echo ""
echo "============================================"
if [ "$FAILURES" -gt 0 ]; then
    echo "  $FAILURES test suite(s) FAILED"
    exit 1
else
    echo "  All test suites PASSED"
    exit 0
fi
