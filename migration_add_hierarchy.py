"""
================================================================================
MIGRATION: ADD HIERARCHICAL TOPIC STRUCTURE
================================================================================

PURPOSE:
Add parent-child hierarchy to the topics table to support two-level topic
categorization (Parent Topic → Subtopic).

WHAT THIS MIGRATION DOES:
1. Adds parent_topic_id column to topics table (foreign key to topics.id)
2. Adds is_parent column to topics table (boolean flag)
3. Creates index on parent_topic_id for efficient lookups
4. Safely handles existing data

CHANGES:
- topics.parent_topic_id: INTEGER (NULL for parent topics, references topics.id for subtopics)
- topics.is_parent: INTEGER (0=subtopic, 1=parent topic) - SQLite uses INTEGER for booleans

EXAMPLE STRUCTURE AFTER MIGRATION:
id | topic_name              | parent_topic_id | is_parent | smb_score
1  | Employment Law          | NULL            | 1         | 10
2  | Wrongful Dismissal      | 1               | 0         | 9
3  | Workplace Safety        | 1               | 0         | 9
4  | Contract Law            | NULL            | 1         | 10
5  | Contract Formation      | 4               | 0         | 9

USAGE:
    python migration_add_hierarchy.py

SAFETY:
- Uses ALTER TABLE (doesn't lose existing data)
- Adds columns with sensible defaults
- All existing topics become subtopics by default (is_parent=0, parent_topic_id=NULL)
- Can be run multiple times safely (checks if columns already exist)
"""

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """
    Check if a column already exists in a table.

    WHAT THIS DOES:
    Queries SQLite's table_info pragma to check if column exists.
    This prevents errors when running migration multiple times.

    RETURNS:
        True if column exists, False otherwise
    """
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_database(db_path: str = 'data/pipeline.db'):
    """
    Add hierarchical structure columns to topics table.

    WHAT THIS DOES:
    1. Checks if database exists
    2. Checks if migration is needed (columns don't exist)
    3. Adds parent_topic_id and is_parent columns
    4. Creates index on parent_topic_id
    5. Reports success

    PARAMETERS:
        db_path: Path to SQLite database file (default: data/pipeline.db)

    MIGRATION DETAILS:
        - parent_topic_id: NULL means this is a parent topic (or has no parent)
        - is_parent: 0 (subtopic) or 1 (parent topic)
        - All existing topics become subtopics by default (is_parent=0)

    EXAMPLE QUERIES AFTER MIGRATION:
        -- Get all parent topics
        SELECT * FROM topics WHERE is_parent = 1;

        -- Get all subtopics for a parent
        SELECT * FROM topics WHERE parent_topic_id = 1;

        -- Get all orphaned subtopics (no parent assigned)
        SELECT * FROM topics WHERE is_parent = 0 AND parent_topic_id IS NULL;
    """

    # CHECK DATABASE EXISTS
    if not Path(db_path).exists():
        logger.error(f"Database not found at {db_path}")
        logger.error("Run fetch.py and compile.py first to create the database")
        return False

    logger.info("=" * 80)
    logger.info("STARTING DATABASE MIGRATION")
    logger.info("=" * 80)
    logger.info(f"Database: {db_path}")

    # CONNECT TO DATABASE
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # CHECK IF MIGRATION ALREADY APPLIED
        parent_topic_id_exists = check_column_exists(cursor, 'topics', 'parent_topic_id')
        is_parent_exists = check_column_exists(cursor, 'topics', 'is_parent')

        if parent_topic_id_exists and is_parent_exists:
            logger.info("Migration already applied. Columns already exist.")
            logger.info("No changes needed.")
            return True

        # ADD parent_topic_id COLUMN
        if not parent_topic_id_exists:
            logger.info("Adding parent_topic_id column...")
            cursor.execute("""
                ALTER TABLE topics
                ADD COLUMN parent_topic_id INTEGER
            """)
            logger.info("✓ Added parent_topic_id column")
        else:
            logger.info("✓ parent_topic_id column already exists")

        # ADD is_parent COLUMN
        if not is_parent_exists:
            logger.info("Adding is_parent column...")
            cursor.execute("""
                ALTER TABLE topics
                ADD COLUMN is_parent INTEGER DEFAULT 0
            """)
            logger.info("✓ Added is_parent column (default: 0 = subtopic)")
        else:
            logger.info("✓ is_parent column already exists")

        # CREATE INDEX FOR EFFICIENT LOOKUPS
        # This makes "find all subtopics for parent X" queries fast
        logger.info("Creating index on parent_topic_id...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_parent_topic_id
                ON topics(parent_topic_id)
            """)
            logger.info("✓ Created index on parent_topic_id")
        except sqlite3.OperationalError:
            logger.info("✓ Index already exists")

        # COMMIT CHANGES
        conn.commit()

        # REPORT CURRENT STATE
        cursor.execute("SELECT COUNT(*) FROM topics")
        total_topics = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM topics WHERE is_parent = 1")
        parent_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM topics WHERE is_parent = 0")
        subtopic_count = cursor.fetchone()[0]

        logger.info("=" * 80)
        logger.info("MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"Total topics: {total_topics}")
        logger.info(f"Parent topics: {parent_count}")
        logger.info(f"Subtopics: {subtopic_count}")
        logger.info("")
        logger.info("NEXT STEPS:")
        logger.info("1. Update compile.py to extract parent + subtopic hierarchy")
        logger.info("2. Update database.py with hierarchical storage logic")
        logger.info("3. Update view_topics.py to display hierarchy")
        logger.info("4. Update generate.py to support parent/subtopic selection")

        return True

    except Exception as e:
        # ROLLBACK ON ERROR
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        return False

    finally:
        # CLOSE CONNECTION
        conn.close()
        logger.info("Database connection closed")


if __name__ == '__main__':
    """
    Run migration when script is executed directly.

    USAGE:
        python migration_add_hierarchy.py

    WHAT HAPPENS:
        - Checks if database exists
        - Adds hierarchy columns if needed
        - Reports success or failure
        - Safe to run multiple times
    """
    success = migrate_database()

    if success:
        print("\n✅ Migration completed successfully!")
        print("Your database now supports hierarchical topics.")
    else:
        print("\n❌ Migration failed. Check the logs above.")
