#!/bin/bash
# Setup script for 3-level hierarchy system

echo "=================================="
echo "3-LEVEL HIERARCHY SETUP"
echo "=================================="
echo ""

# Step 1: Run migration
echo "Step 1: Running database migration..."
python migration_add_article_tags_and_tracking.py
if [ $? -ne 0 ]; then
    echo "❌ Migration failed!"
    exit 1
fi
echo ""

# Step 2: Reset topics
echo "Step 2: Resetting topics..."
echo "⚠️  This will delete all existing topics and mark articles as unprocessed."
read -p "Continue? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "❌ Setup cancelled."
    exit 1
fi

sqlite3 data/pipeline.db <<EOF
DELETE FROM article_topics;
DELETE FROM topics;
UPDATE articles SET processed = 0;
EOF

echo "✅ Topics reset complete"
echo ""

# Step 3: Reprocess articles
echo "Step 3: Reprocessing articles with 3-level hierarchy..."
echo "This will extract: Parent > Subtopic > Article Tag"
echo ""
python compile.py
if [ $? -ne 0 ]; then
    echo "❌ Processing failed!"
    exit 1
fi
echo ""

# Step 4: Show results
echo "=================================="
echo "✅ SETUP COMPLETE!"
echo "=================================="
echo ""
echo "Your database now has:"
echo "  - 3-level topic hierarchy"
echo "  - Generation tracking"
echo "  - Grouped subtopics (multiple articles per subtopic)"
echo ""
echo "Next steps:"
echo "  1. View hierarchy:  python control_center.py → 3 → 1"
echo "  2. Generate article: python control_center.py → 4 → 1"
echo ""
echo "Documentation: See 3_LEVEL_HIERARCHY_GUIDE.md"
