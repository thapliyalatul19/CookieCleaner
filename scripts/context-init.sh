#!/bin/bash
set -e

echo "🚀 Bootstrapping Context Architecture for Cookie Cleaner..."

# Check Memory Bank files
echo "📝 Checking Memory Bank files..."
for f in .context/*.md; do
    if [ -f "$f" ]; then
        echo "✅ $(basename $f) exists."
    fi
done

# Check validation script
if [ -f scripts/validate-context.sh ]; then
    echo "✅ Validation script exists."
fi

# Check pre-commit hook
if [ -f .git/hooks/pre-commit ]; then
    echo "✅ Pre-commit hook installed."
fi

echo ""
echo "🎉 Bootstrap verification complete!"
echo ""
echo "Next Steps:"
echo "  1. Review CLAUDE.md (the constitution)"
echo "  2. Read Memory Bank: cat .context/*.md"
echo "  3. Start Phase 1 implementation"
