#!/bin/bash

# Cookie Cleaner - Context Validation Script
# Enforces Memory Bank integrity and Supervisor Mode rules

# 1. Ensure Memory Bank files are not empty
echo "Validating Memory Bank files..."
for f in .context/*.md; do
  if [ ! -s "$f" ]; then
    echo "❌ Validation Error: $f is empty or missing."
    echo "   Memory Bank files must contain content."
    exit 1
  fi
done

# 2. Supervisor-mode guard (prevents Supervisor from committing source changes)
if [ "${SUPERVISOR_MODE:-0}" = "1" ]; then
  echo "Checking Supervisor Mode constraints..."
  if git diff --cached --name-only | grep -E "^(src/|lib/|app/)" >/dev/null 2>&1; then
    echo "❌ SUPERVISOR VIOLATION: source file changes staged while SUPERVISOR_MODE=1."
    echo "   Supervisor must emit patch/diff and instruct Worker to apply."
    echo "   Blocked files:"
    git diff --cached --name-only | grep -E "^(src/|lib/|app/)"
    exit 1
  fi
  echo "✅ Supervisor Mode: No prohibited changes detected."
fi

echo "✅ Context Validated."
exit 0
