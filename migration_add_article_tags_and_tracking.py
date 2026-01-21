"""
================================================================================
MIGRATION: ADD ARTICLE TAGS & GENERATION TRACKING
================================================================================

PURPOSE:
1. Add 3-level hierarchy support (parent → subtopic → article tag)
2. Track which topics have been generated to avoid duplicates

CHANGES:
1. Add `article_tag` column to article_topics table
2. Create `generated_articles` table to track generations

EXAMPLE STRUCTURE:
Parent: Employment Law
├── Subtopic: Wrongful Dismissal
    ├── Article 1: "Wrongful dismissal during protected leave"
    ├── Article 2: "Severance calculations for wrongful dismissal"
    └── Article 3: "Constructive dismissal vs wrongful dismissal"

USAGE:
    python migration_add_article_tags_and_tracking.py
"""

import sqlite3
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column already exists in a table."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def check_table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    """Check if a table exists."""
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
    return cursor.fetchone() is not None


def migrate_database(db_path: str = 'data/pipeline.db'):
    """
    Add article tags and generation tracking.
    """

    if not Path(db_path).exists():
        logger.error(f"Database not found at {db_path}")
        return False

    logger.info("=" * 80)
    logger.info("STARTING MIGRATION: ARTICLE TAGS & GENERATION TRACKING")
    logger.info("=" * 80)
    logger.info(f"Database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # ADD article_tag COLUMN TO article_topics
        if not check_column_exists(cursor, 'article_topics', 'article_tag'):
            logger.info("Adding article_tag column to article_topics...")
            cursor.execute("""
                ALTER TABLE article_topics
                ADD COLUMN article_tag TEXT
            """)
            logger.info("✓ Added article_tag column")
        else:
            logger.info("✓ article_tag column already exists")

        # CREATE generated_articles TABLE
        if not check_table_exists(cursor, 'generated_articles'):
            logger.info("Creating generated_articles table...")
            cursor.execute("""
                CREATE TABLE generated_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL,
                    generated_date TEXT NOT NULL,
                    output_file TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    source_article_count INTEGER NOT NULL,
                    word_count INTEGER,
                    FOREIGN KEY (topic_id) REFERENCES topics(id)
                )
            """)
            logger.info("✓ Created generated_articles table")
        else:
            logger.info("✓ generated_articles table already exists")

        # CREATE INDEX FOR EFFICIENT LOOKUPS
        logger.info("Creating index on generated_articles...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_generated_topic_id
                ON generated_articles(topic_id)
            """)
            logger.info("✓ Created index on topic_id")
        except sqlite3.OperationalError:
            logger.info("✓ Index already exists")

        # COMMIT CHANGES
        conn.commit()

        # REPORT STATUS
        cursor.execute("SELECT COUNT(*) FROM article_topics WHERE article_tag IS NOT NULL")
        tagged_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM generated_articles")
        generated_count = cursor.fetchone()[0]

        logger.info("=" * 80)
        logger.info("MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Articles with tags: {tagged_count}")
        logger.info(f"Generated articles tracked: {generated_count}")
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("1. Reset and reprocess articles to add article tags")
        logger.info("2. Generated articles will be automatically tracked")

        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        return False

    finally:
        conn.close()
        logger.info("Database connection closed")


if __name__ == '__main__':
    success = migrate_database()

    if success:
        print("\n✅ Migration completed successfully!")
        print("Your database now supports:")
        print("  - 3-level hierarchy (parent → subtopic → article tag)")
        print("  - Generation tracking to avoid duplicates")
    else:
        print("\n❌ Migration failed. Check the logs above.")
