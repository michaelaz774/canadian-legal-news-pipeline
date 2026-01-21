"""
Database module for Canadian Legal News Pipeline
Handles SQLite operations for articles, topics, and their relationships

KEY CONCEPTS:
- SQLite: A lightweight database stored in a single file (no server needed)
- Row Factory: Allows us to access database results as dictionaries instead of tuples
- UNIQUE constraint: Database-level prevention of duplicate entries
- Many-to-many relationship: Articles can have multiple topics, topics can have multiple articles
"""

import sqlite3
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging
import os

# Set up logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    """
    Database class that manages all SQLite operations.

    DESIGN PHILOSOPHY:
    - Single responsibility: This class only handles database operations
    - Automatic duplicate prevention: Database constraints handle duplicates
    - Graceful error handling: Log errors and continue processing
    - Dictionary-based interface: Easy to work with in Python
    """

    def __init__(self, db_path=None):
        """
        Initialize database connection and create tables if needed.

        WHAT HAPPENS HERE:
        1. Determines database path (Railway persistent volume or local)
        2. Creates the data directory if it doesn't exist
        3. Opens a connection to the SQLite database file
        4. Sets row_factory so results come back as dictionaries (not tuples)
        5. Calls _create_tables() to ensure schema exists

        Args:
            db_path: Path to SQLite database file (default: auto-detect Railway or local)
        """
        # Auto-detect environment and set appropriate database path
        if db_path is None:
            if os.path.exists('/data'):
                # Railway environment - use persistent volume
                db_path = '/data/pipeline.db'
                logger.info("Railway environment detected - using persistent volume at /data/pipeline.db")
            else:
                # Local development
                db_path = 'data/pipeline.db'
                logger.info("Local environment detected - using data/pipeline.db")

        # Ensure data directory exists (os.makedirs with exist_ok=True won't error if it exists)
        data_dir = os.path.dirname(db_path)
        if data_dir:  # Only create directory if path has a directory component
            os.makedirs(data_dir, exist_ok=True)

        self.db_path = db_path
        # Connect to SQLite database (creates file if it doesn't exist)
        self.conn = sqlite3.connect(db_path)

        # IMPORTANT: row_factory makes results return as sqlite3.Row objects
        # which can be converted to dictionaries. Without this, you'd get tuples.
        # Example without row_factory: (1, 'http://...', 'Title', ...)
        # Example with row_factory: {'id': 1, 'url': 'http://...', 'title': 'Title', ...}
        self.conn.row_factory = sqlite3.Row

        # Create tables if they don't exist yet
        self._create_tables()
        logger.info(f"Database initialized at {db_path}")

    def _create_tables(self):
        """
        Create database tables if they don't exist.

        SCHEMA DESIGN EXPLAINED:

        1. ARTICLES TABLE:
           - Stores all fetched articles from various sources
           - url is UNIQUE to prevent duplicates (database enforces this)
           - processed flag tracks whether we've extracted topics yet

        2. TOPICS TABLE:
           - Stores normalized legal topics (case names, legislation, etc.)
           - topic_name is UNIQUE so "Smith v. Jones" only exists once
           - smb_relevance_score (0-10) helps prioritize topics for generation

        3. ARTICLE_TOPICS TABLE (join table):
           - Implements many-to-many relationship
           - One article can discuss multiple topics
           - One topic can appear in multiple articles
           - PRIMARY KEY (article_id, topic_id) prevents duplicate links
        """
        cursor = self.conn.cursor()

        # ============ ARTICLES TABLE ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                summary TEXT,
                source TEXT NOT NULL,
                published_date TEXT,
                fetched_date TEXT NOT NULL,
                processed INTEGER DEFAULT 0
            )
        """)
        # EXPLANATION OF COLUMNS:
        # - id: Auto-incrementing primary key (1, 2, 3, ...)
        # - url: UNIQUE constraint prevents same URL from being inserted twice
        # - title: Article headline
        # - content: Full article text (extracted from webpage)
        # - summary: Brief summary (often from RSS feed)
        # - source: Which website/feed this came from (e.g., "Slaw", "CanLII")
        # - published_date: When the article was published (varies by source)
        # - fetched_date: When we collected it (ISO format: "2026-01-13T10:30:00")
        # - processed: 0 = not yet analyzed for topics, 1 = topics extracted

        # ============ TOPICS TABLE ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_name TEXT UNIQUE NOT NULL,
                category TEXT,
                key_entity TEXT,
                smb_relevance_score INTEGER,
                parent_topic_id INTEGER,
                is_parent INTEGER DEFAULT 0,
                created_date TEXT NOT NULL,
                FOREIGN KEY (parent_topic_id) REFERENCES topics(id)
            )
        """)
        # EXPLANATION OF COLUMNS:
        # - id: Auto-incrementing primary key
        # - topic_name: UNIQUE normalized name (e.g., "Smith v. Jones - Wrongful Dismissal")
        #   The LLM in compile.py will normalize variations of the same topic to this name
        # - category: Legal area (e.g., "employment law", "corporate law")
        # - key_entity: Case citation, bill number, etc. (e.g., "Smith v. Jones")
        # - smb_relevance_score: 0-10 score from LLM indicating relevance to small-medium businesses
        #   8-10 = highly relevant (direct SMB impact)
        #   5-7 = moderately relevant
        #   0-4 = low relevance (complex matters, large enterprise only)
        # - created_date: When this topic was first identified

        # ============ ARTICLE_TOPICS JOIN TABLE ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_topics (
                article_id INTEGER NOT NULL,
                topic_id INTEGER NOT NULL,
                article_tag TEXT,
                created_date TEXT NOT NULL,
                PRIMARY KEY (article_id, topic_id),
                FOREIGN KEY (article_id) REFERENCES articles(id),
                FOREIGN KEY (topic_id) REFERENCES topics(id)
            )
        """)
        # EXPLANATION:
        # - This is a "join table" or "junction table" for many-to-many relationships
        # - PRIMARY KEY (article_id, topic_id) means each article-topic pair can only exist once
        # - FOREIGN KEY constraints ensure referential integrity (can't link to non-existent articles/topics)
        #
        # EXAMPLE SCENARIO:
        # Article 1 (Slaw) discusses "Smith v. Jones" → Link: (1, 5)
        # Article 2 (McCarthy) discusses "Smith v. Jones" → Link: (2, 5)
        # Article 2 also discusses "Bill C-27" → Link: (2, 8)
        #
        # Query: "Show me all articles about Smith v. Jones" → Returns articles 1 and 2
        # Query: "Show me all topics in article 2" → Returns "Smith v. Jones" and "Bill C-27"

        # ============ GENERATED_ARTICLES TABLE ============
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS generated_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                generated_date TEXT NOT NULL,
                output_file TEXT NOT NULL,
                model_used TEXT NOT NULL,
                source_article_count INTEGER,
                word_count INTEGER,
                FOREIGN KEY (topic_id) REFERENCES topics(id)
            )
        """)
        # EXPLANATION:
        # - Tracks which topics have been generated into articles
        # - Prevents duplicate generation of the same topic
        # - Records metadata about the generation process

        self.conn.commit()
        logger.debug("Database tables created/verified")

        # Run migrations to add any missing columns
        self._run_migrations()

    def _run_migrations(self):
        """
        Run database migrations to add missing columns to existing tables.

        WHY THIS EXISTS:
        - Production databases may have been created with older schemas
        - This ensures all required columns exist without dropping/recreating tables
        - Safe to run multiple times (checks if column exists before adding)
        """
        cursor = self.conn.cursor()

        # Check if topics table has parent_topic_id and is_parent columns
        cursor.execute("PRAGMA table_info(topics)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add parent_topic_id if missing
        if 'parent_topic_id' not in columns:
            msg = "Adding parent_topic_id column to topics table..."
            logger.info(msg)
            print(msg, flush=True)
            cursor.execute("ALTER TABLE topics ADD COLUMN parent_topic_id INTEGER")
            self.conn.commit()
            msg = "✓ Added parent_topic_id column"
            logger.info(msg)
            print(msg, flush=True)

        # Add is_parent if missing
        if 'is_parent' not in columns:
            msg = "Adding is_parent column to topics table..."
            logger.info(msg)
            print(msg, flush=True)
            cursor.execute("ALTER TABLE topics ADD COLUMN is_parent INTEGER DEFAULT 0")
            self.conn.commit()
            msg = "✓ Added is_parent column"
            logger.info(msg)
            print(msg, flush=True)

        # Check if article_topics table has article_tag column
        cursor.execute("PRAGMA table_info(article_topics)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add article_tag if missing
        if 'article_tag' not in columns:
            msg = "Adding article_tag column to article_topics table..."
            logger.info(msg)
            print(msg, flush=True)
            cursor.execute("ALTER TABLE article_topics ADD COLUMN article_tag TEXT")
            self.conn.commit()
            msg = "✓ Added article_tag column"
            logger.info(msg)
            print(msg, flush=True)

    # ============================================================================
    # ARTICLE OPERATIONS
    # These methods handle inserting, retrieving, and updating articles
    # ============================================================================

    def insert_article(self, article: Dict) -> Optional[int]:
        """
        Insert a single article into the database.

        DUPLICATE HANDLING:
        - The UNIQUE constraint on the 'url' column prevents duplicates
        - If URL already exists, sqlite3.IntegrityError is raised
        - We catch this error and return None instead of crashing

        WHY THIS APPROACH:
        - Database-level enforcement is more reliable than application logic
        - Even if multiple processes try to insert the same URL, DB prevents duplicates
        - Simple: We don't need to check "does this exist?" before inserting

        Args:
            article: Dictionary with keys: url, title, source, content (optional),
                    summary (optional), published_date (optional), fetched_date (optional)

        Returns:
            Article ID (integer) if successful, None if duplicate or error

        EXAMPLE USAGE:
            article = {
                'url': 'https://slaw.ca/2025/01/10/article',
                'title': 'New Employment Law Changes',
                'source': 'Slaw',
                'content': 'Full article text here...',
                'fetched_date': '2026-01-13T10:30:00'
            }
            article_id = db.insert_article(article)
            if article_id:
                print(f"Inserted with ID {article_id}")
            else:
                print("Duplicate or error")
        """
        try:
            cursor = self.conn.execute("""
                INSERT INTO articles (
                    url, title, content, summary, source,
                    published_date, fetched_date, processed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                article['url'],
                article['title'],
                article.get('content', ''),  # .get() returns '' if 'content' key doesn't exist
                article.get('summary', ''),
                article['source'],
                article.get('published_date', ''),
                article.get('fetched_date', datetime.now().isoformat())
            ))
            # NOTATION: The ? placeholders are for parameterized queries
            # This prevents SQL injection attacks
            # BAD:  f"INSERT INTO articles VALUES ('{article['url']}')"  ← SQL injection risk!
            # GOOD: "INSERT INTO articles VALUES (?)", (article['url'],)  ← Safe

            self.conn.commit()  # Save changes to disk
            logger.debug(f"Inserted article: {article['url']}")
            return cursor.lastrowid  # Returns the ID of the inserted row

        except sqlite3.IntegrityError:
            # This exception fires when UNIQUE constraint is violated (duplicate URL)
            logger.debug(f"Skipping duplicate URL: {article['url']}")
            return None

        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Error inserting article {article.get('url', 'unknown')}: {e}")
            return None

    def insert_articles_batch(self, articles: List[Dict]) -> Tuple[int, int]:
        """
        Insert multiple articles, automatically skipping duplicates.

        WHY BATCH INSERTION:
        - More efficient than calling insert_article() in a loop
        - Returns summary statistics (inserted vs skipped)
        - Continues processing even if some articles fail

        DUPLICATE PREVENTION MECHANISM:
        1. Database has UNIQUE constraint on url column
        2. When we try to insert a duplicate URL, database raises IntegrityError
        3. We catch the error, increment skipped counter, continue to next article
        4. User sees: "Inserted: 5, Skipped: 15" (15 were already in database)

        This is IDEMPOTENT: You can run fetch.py multiple times safely.
        First run: Inserted: 80, Skipped: 0
        Second run: Inserted: 0, Skipped: 80
        Third run (with 2 new articles): Inserted: 2, Skipped: 80

        Returns:
            Tuple[int, int]: (inserted_count, skipped_count)

        EXAMPLE USAGE:
            articles = [
                {'url': 'http://site.com/1', 'title': 'Article 1', 'source': 'Site', 'fetched_date': '...'},
                {'url': 'http://site.com/2', 'title': 'Article 2', 'source': 'Site', 'fetched_date': '...'},
            ]
            inserted, skipped = db.insert_articles_batch(articles)
            print(f"Inserted: {inserted}, Skipped: {skipped}")
        """
        inserted = 0
        skipped = 0

        for article in articles:
            try:
                cursor = self.conn.execute("""
                    INSERT INTO articles (
                        url, title, content, summary, source,
                        published_date, fetched_date, processed
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    article['url'],
                    article['title'],
                    article.get('content', ''),
                    article.get('summary', ''),
                    article['source'],
                    article.get('published_date', ''),
                    article['fetched_date']
                ))
                self.conn.commit()
                inserted += 1
                logger.debug(f"Inserted article: {article['url']}")

            except sqlite3.IntegrityError:
                # URL already exists - this is EXPECTED on subsequent runs
                skipped += 1
                logger.debug(f"Skipping duplicate URL: {article['url']}")
                continue  # Move to next article

            except Exception as e:
                # Unexpected error - log and skip this article
                logger.error(f"Error inserting article {article.get('url', 'unknown')}: {e}")
                skipped += 1
                continue

        return inserted, skipped

    def get_unprocessed_articles(self) -> List[Dict]:
        """
        Get all articles that haven't been processed for topic extraction.

        WHEN THIS IS USED:
        - compile.py calls this to get articles that need topic extraction
        - After extracting topics, we mark the article as processed (processed=1)
        - Next time compile.py runs, it only processes NEW articles

        WHY THIS MATTERS:
        - Avoids re-processing articles (saves API costs)
        - compile.py can be run incrementally as new articles arrive

        FLOW:
        1. fetch.py inserts new articles with processed=0
        2. compile.py calls get_unprocessed_articles() → returns only processed=0
        3. compile.py extracts topics from each article
        4. compile.py calls mark_article_processed() → sets processed=1
        5. Next run of compile.py skips these articles

        Returns:
            List of dictionaries, one per article
        """
        cursor = self.conn.execute("""
            SELECT * FROM articles WHERE processed = 0
        """)

        # Convert sqlite3.Row objects to dictionaries
        # cursor.description gives us column names: ['id', 'url', 'title', ...]
        columns = [col[0] for col in cursor.description]
        # zip() pairs up column names with values from each row
        # dict(zip(...)) creates a dictionary: {'id': 1, 'url': 'http://...', ...}
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def mark_article_processed(self, article_id: int):
        """
        Mark an article as processed after topic extraction.

        SIMPLE BUT CRITICAL:
        - Changes processed flag from 0 to 1
        - Ensures we don't re-process the same article on next compile.py run
        - Called at the end of process_article() in compile.py

        Args:
            article_id: The ID of the article to mark as processed
        """
        self.conn.execute("""
            UPDATE articles SET processed = 1 WHERE id = ?
        """, (article_id,))
        self.conn.commit()
        logger.debug(f"Marked article {article_id} as processed")

    def get_article_by_id(self, article_id: int) -> Optional[Dict]:
        """
        Get a single article by its ID.

        WHEN THIS IS USED:
        - When you need to look up details about a specific article
        - Less common than get_articles_for_topic()

        Returns:
            Dictionary with article data, or None if not found
        """
        cursor = self.conn.execute("""
            SELECT * FROM articles WHERE id = ?
        """, (article_id,))

        row = cursor.fetchone()  # fetchone() returns a single row or None
        if row:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return None

    # ============================================================================
    # TOPIC OPERATIONS
    # These methods handle topics (normalized legal topics extracted by LLM)
    # ============================================================================

    def find_topic_by_name(self, topic_name: str) -> Optional[Dict]:
        """
        Find a topic by its exact name.

        WHY THIS EXISTS:
        - Before creating a new topic, we check if it already exists
        - LLM normalizes topic names, so "Smith v Jones" should map to same topic
        - Used internally by find_or_create_topic()

        Returns:
            Dictionary with topic data, or None if not found
        """
        cursor = self.conn.execute("""
            SELECT * FROM topics WHERE topic_name = ?
        """, (topic_name,))

        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return None

    def insert_topic(self, topic_name: str, category: str = '',
                     key_entity: str = '', smb_relevance_score: int = 5,
                     parent_topic_id: Optional[int] = None, is_parent: bool = False) -> int:
        """
        Insert a new topic into the database.

        PARAMETERS EXPLAINED:
        - topic_name: Normalized name (e.g., "Smith v. Jones - Wrongful Dismissal")
        - category: Legal area (e.g., "employment law", "corporate law")
        - key_entity: Case citation or bill number (e.g., "Smith v. Jones", "Bill C-27")
        - smb_relevance_score: 0-10 score indicating relevance to SMBs (default: 5)

        SMB RELEVANCE SCORE:
        - 8-10: Highly relevant (employment law, corporate governance, contracts)
        - 5-7: Moderately relevant (useful but not urgent)
        - 0-4: Low relevance (complex M&A, securities law, large enterprise)

        Returns:
            Topic ID (integer)
        """
        cursor = self.conn.execute("""
            INSERT INTO topics (
                topic_name, category, key_entity, smb_relevance_score,
                parent_topic_id, is_parent, created_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            topic_name,
            category,
            key_entity,
            smb_relevance_score,
            parent_topic_id,
            1 if is_parent else 0,  # SQLite uses INTEGER for booleans
            datetime.now().isoformat()  # ISO format: "2026-01-13T10:30:00.123456"
        ))
        self.conn.commit()

        # Log with hierarchy info
        if is_parent:
            logger.debug(f"Inserted parent topic: {topic_name} (SMB score: {smb_relevance_score})")
        else:
            logger.debug(f"Inserted subtopic: {topic_name} (parent_id: {parent_topic_id}, SMB score: {smb_relevance_score})")

        return cursor.lastrowid

    def find_or_create_topic(self, topic_name: str, category: str = '',
                            key_entity: str = '', smb_relevance_score: int = 5,
                            parent_topic_id: Optional[int] = None, is_parent: bool = False) -> int:
        """
        Find existing topic by name, or create if it doesn't exist.

        THIS IS THE KEY METHOD FOR TOPIC NORMALIZATION:

        SCENARIO:
        - Article 1 from Slaw mentions "Smith v Jones wrongful dismissal"
        - Article 2 from McCarthy mentions "Smith v. Jones - wrongful dismissal case"
        - LLM in compile.py normalizes both to "Smith v. Jones - Wrongful Dismissal"
        - This method ensures both articles link to the SAME topic in database

        FLOW:
        1. Check if topic already exists (by exact name match)
        2. If exists: Return existing topic ID
        3. If not exists: Create new topic, return new ID

        WHY THIS MATTERS:
        - Prevents duplicate topics with slightly different names
        - Enables many-to-many relationship (multiple articles → one topic)
        - When generating articles, we pull from all articles with this topic

        Returns:
            Topic ID (integer)

        USAGE IN compile.py:
            topic_id = db.find_or_create_topic(
                topic_name="Smith v. Jones - Wrongful Dismissal",
                category="employment law",
                key_entity="Smith v. Jones",
                smb_relevance_score=9
            )
            db.link_article_to_topic(article_id, topic_id)
        """
        # Try to find existing topic
        existing = self.find_topic_by_name(topic_name)

        if existing:
            # Topic already exists, return its ID
            return existing['id']

        # Topic doesn't exist, create it
        return self.insert_topic(topic_name, category, key_entity, smb_relevance_score,
                                parent_topic_id, is_parent)

    def get_parent_topics(self) -> List[Dict]:
        """
        Get all parent topics (topics with is_parent=1).

        WHAT THIS RETURNS:
        - All topics that are parents (not subtopics)
        - Includes article count (inherited from subtopics)
        - Sorted by creation date (newest first)

        WHEN THIS IS USED:
        - view_topics.py to show topic hierarchy
        - generate.py to browse by parent category

        Returns:
            List of dictionaries, one per parent topic
        """
        cursor = self.conn.execute("""
            SELECT
                t.*,
                COUNT(DISTINCT at2.article_id) as article_count
            FROM topics t
            LEFT JOIN topics subtopics ON subtopics.parent_topic_id = t.id
            LEFT JOIN article_topics at2 ON subtopics.id = at2.topic_id
            WHERE t.is_parent = 1
            GROUP BY t.id
            ORDER BY t.created_date DESC
        """)
        # SQL BREAKDOWN:
        # - Join to subtopics that belong to this parent (subtopics.parent_topic_id = t.id)
        # - Join to articles linked to those subtopics (subtopics.id = at2.topic_id)
        # - Count distinct article IDs from all subtopics under this parent

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_subtopics_for_parent(self, parent_topic_id: int) -> List[Dict]:
        """
        Get all subtopics for a specific parent topic.

        WHAT THIS RETURNS:
        - All topics with parent_topic_id matching the given parent
        - Includes article count for each subtopic
        - Sorted by article count (most articles first)

        WHEN THIS IS USED:
        - view_topics.py to show subtopics under a parent
        - generate.py to select specific subtopics

        PARAMETERS:
            parent_topic_id: ID of the parent topic

        Returns:
            List of dictionaries, one per subtopic

        EXAMPLE:
            subtopics = db.get_subtopics_for_parent(1)  # Get Employment Law subtopics
            # Returns: Wrongful Dismissal, Workplace Safety, etc.
        """
        cursor = self.conn.execute("""
            SELECT
                t.*,
                COUNT(at.article_id) as article_count
            FROM topics t
            LEFT JOIN article_topics at ON t.id = at.topic_id
            WHERE t.parent_topic_id = ?
            GROUP BY t.id
            ORDER BY article_count DESC
        """, (parent_topic_id,))

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_all_topics(self) -> List[Dict]:
        """
        Get all topics with basic metadata.

        WHAT THIS RETURNS:
        - All topics from database (both parents and subtopics)
        - Each topic includes article_count (how many articles discuss it)
        - Sorted by creation date (newest first)

        WHEN THIS IS USED:
        - view_topics.py uses this to show all topics
        - generate.py uses this to filter topics for article generation

        Returns:
            List of dictionaries, one per topic
        """
        cursor = self.conn.execute("""
            SELECT
                t.*,
                COUNT(at.article_id) as article_count
            FROM topics t
            LEFT JOIN article_topics at ON t.id = at.topic_id
            GROUP BY t.id
            ORDER BY t.created_date DESC
        """)
        # SQL BREAKDOWN:
        # - SELECT t.*: Get all columns from topics table
        # - COUNT(at.article_id): Count how many articles are linked to this topic
        # - LEFT JOIN: Include topics even if they have zero articles (shouldn't happen, but safe)
        # - GROUP BY t.id: One row per topic (aggregate the article count)
        # - ORDER BY: Newest topics first

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_topic_by_id(self, topic_id: int) -> Optional[Dict]:
        """
        Get single topic by ID with metadata.

        SIMPLE WRAPPER:
        - Gets all topics with metadata
        - Filters to find the one with matching ID
        - Returns None if not found
        """
        topics = self.get_topics_with_metadata()
        # next() finds first matching item, returns None if no match
        return next((t for t in topics if t['id'] == topic_id), None)

    def get_topics_with_metadata(self) -> List[Dict]:
        """
        Get all topics with comprehensive metadata.

        METADATA INCLUDED:
        - article_count: How many articles discuss this topic
        - earliest_date: When the first article about this topic was published
        - latest_date: When the most recent article was published

        WHY THIS IS USEFUL:
        - view_topics.py shows date ranges to indicate topic freshness
        - Can filter for "topics from last 30 days"
        - Can sort by "most articles" or "most recent"

        EXAMPLE OUTPUT:
        [
            {
                'id': 12,
                'topic_name': 'Smith v. Jones - Wrongful Dismissal',
                'category': 'employment law',
                'smb_relevance_score': 9,
                'article_count': 4,
                'earliest_date': '2025-01-10',
                'latest_date': '2025-01-12'
            },
            ...
        ]
        """
        query = """
            SELECT
                t.id,
                t.topic_name,
                t.category,
                t.key_entity,
                t.smb_relevance_score,
                t.created_date,
                COUNT(at.article_id) as article_count,
                MIN(a.published_date) as earliest_date,
                MAX(a.published_date) as latest_date
            FROM topics t
            LEFT JOIN article_topics at ON t.id = at.topic_id
            LEFT JOIN articles a ON at.article_id = a.id
            GROUP BY t.id
            ORDER BY t.created_date DESC
        """
        # SQL BREAKDOWN:
        # - MIN(a.published_date): Earliest article date for this topic
        # - MAX(a.published_date): Latest article date for this topic
        # - Two joins: topics → article_topics → articles
        # - GROUP BY aggregates all articles for each topic into one row

        cursor = self.conn.execute(query)
        columns = [col[0] for col in cursor.description]

        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # ============================================================================
    # LINK OPERATIONS
    # These methods manage the many-to-many relationship between articles and topics
    # ============================================================================

    def link_article_to_topic(self, article_id: int, topic_id: int, article_tag: Optional[str] = None):
        """
        Create a link between an article and a topic with optional article tag.

        WHEN THIS IS USED:
        - compile.py extracts topics from an article
        - For each topic, it creates a link: article → topic
        - One article can be linked to multiple topics
        - Article tag identifies the specific aspect discussed in this article

        DUPLICATE PREVENTION:
        - PRIMARY KEY (article_id, topic_id) prevents duplicate links
        - If link already exists, IntegrityError is raised (we catch and ignore)

        EXAMPLE SCENARIO:
        Article 5 discusses "Wrongful Dismissal" with tag "During pregnancy leave"
        Article 6 discusses "Wrongful Dismissal" with tag "Constructive dismissal"
        Both link to same subtopic but with different tags
        """
        try:
            self.conn.execute("""
                INSERT INTO article_topics (article_id, topic_id, article_tag, created_date)
                VALUES (?, ?, ?, ?)
            """, (article_id, topic_id, article_tag, datetime.now().isoformat()))
            self.conn.commit()
            logger.debug(f"Linked article {article_id} to topic {topic_id} [{article_tag}]")

        except sqlite3.IntegrityError:
            # Link already exists - this is fine, just skip
            logger.debug(f"Link already exists: article {article_id} → topic {topic_id}")

    def get_articles_for_topic(self, topic_id: int) -> List[Dict]:
        """
        Get all articles linked to a specific topic.

        WHEN THIS IS USED:
        - generate.py calls this to get all source articles for a topic
        - Example: "Get all articles about Smith v. Jones"
        - Returns full article data (title, content, url, source, etc.)

        WHY THIS MATTERS:
        - This is how we collect multiple perspectives on the same topic
        - generate.py sends all these articles to Claude for synthesis
        - Result: Comprehensive article combining insights from multiple sources

        EXAMPLE:
        Topic 12: "Smith v. Jones - Wrongful Dismissal"
        Returns:
        [
            {'id': 1, 'title': 'Analysis from Slaw', 'source': 'Slaw', ...},
            {'id': 5, 'title': 'Commentary from McCarthy', 'source': 'McCarthy Tétrault', ...},
            {'id': 8, 'title': 'Case breakdown from Monkhouse', 'source': 'Monkhouse Law', ...}
        ]
        """
        cursor = self.conn.execute("""
            SELECT a.*
            FROM articles a
            JOIN article_topics at ON a.id = at.article_id
            WHERE at.topic_id = ?
            ORDER BY a.published_date DESC
        """, (topic_id,))
        # SQL BREAKDOWN:
        # - Start from articles table
        # - JOIN through article_topics to filter by topic
        # - WHERE filters to specific topic
        # - ORDER BY puts newest articles first

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_topics_for_article(self, article_id: int) -> List[Dict]:
        """
        Get all topics linked to a specific article.

        WHEN THIS IS USED:
        - Less common than get_articles_for_topic()
        - Useful for debugging: "What topics did we extract from article 5?"
        - Could be used for article detail pages in a UI

        Returns:
            List of topic dictionaries
        """
        cursor = self.conn.execute("""
            SELECT t.*
            FROM topics t
            JOIN article_topics at ON t.id = at.topic_id
            WHERE at.article_id = ?
        """, (article_id,))

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # ============================================================================
    # STATS
    # Monitoring and debugging methods
    # ============================================================================

    def get_stats(self) -> Dict:
        """
        Get database statistics for monitoring.

        WHAT THIS RETURNS:
        {
            'total_articles': 80,
            'unprocessed_articles': 0,
            'total_topics': 25,
            'total_links': 120
        }

        WHEN THIS IS USED:
        - End of fetch.py: "Database now has 80 total articles"
        - End of compile.py: "Created 25 topics with 120 links"
        - Debugging: Check if pipeline is working correctly
        """
        stats = {}

        # Total articles
        cursor = self.conn.execute("SELECT COUNT(*) FROM articles")
        stats['total_articles'] = cursor.fetchone()[0]

        # Unprocessed articles (need topic extraction)
        cursor = self.conn.execute("SELECT COUNT(*) FROM articles WHERE processed = 0")
        stats['unprocessed_articles'] = cursor.fetchone()[0]

        # Total topics
        cursor = self.conn.execute("SELECT COUNT(*) FROM topics")
        stats['total_topics'] = cursor.fetchone()[0]

        # Total links (article-topic pairs)
        cursor = self.conn.execute("SELECT COUNT(*) FROM article_topics")
        stats['total_links'] = cursor.fetchone()[0]

        return stats

    def track_generation(self, topic_id: int, output_file: str, model_used: str,
                        source_article_count: int, word_count: Optional[int] = None):
        """
        Track a generated article to avoid regenerating the same topic.

        WHEN THIS IS USED:
        - generate.py calls this after successfully generating an article
        - Allows us to see which topics have been generated
        - Can filter out already-generated topics in UI

        PARAMETERS:
            topic_id: The subtopic ID that was generated
            output_file: Path to the generated article
            model_used: Claude model used (sonnet/haiku)
            source_article_count: Number of source articles used
            word_count: Word count of generated article (optional)
        """
        try:
            self.conn.execute("""
                INSERT INTO generated_articles (
                    topic_id, generated_date, output_file, model_used,
                    source_article_count, word_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                topic_id,
                datetime.now().isoformat(),
                output_file,
                model_used,
                source_article_count,
                word_count
            ))
            self.conn.commit()
            logger.info(f"Tracked generation for topic {topic_id}: {output_file}")

        except Exception as e:
            logger.error(f"Failed to track generation: {e}")

    def get_generated_topics(self) -> List[int]:
        """
        Get list of topic IDs that have been generated.

        RETURNS:
            List of topic IDs (subtopics) that have been generated
        """
        cursor = self.conn.execute("""
            SELECT DISTINCT topic_id FROM generated_articles
        """)
        return [row[0] for row in cursor.fetchall()]

    def is_topic_generated(self, topic_id: int) -> bool:
        """
        Check if a topic has been generated.

        PARAMETERS:
            topic_id: The subtopic ID to check

        RETURNS:
            True if topic has been generated, False otherwise
        """
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM generated_articles WHERE topic_id = ?
        """, (topic_id,))
        count = cursor.fetchone()[0]
        return count > 0

    def get_generation_info(self, topic_id: int) -> Optional[Dict]:
        """
        Get generation information for a topic.

        RETURNS:
            Dictionary with generation details, or None if not generated
        """
        cursor = self.conn.execute("""
            SELECT * FROM generated_articles
            WHERE topic_id = ?
            ORDER BY generated_date DESC
            LIMIT 1
        """, (topic_id,))

        row = cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return None

    def get_ungenerated_subtopics(self, min_score: int = 8, min_articles: int = 3) -> List[Dict]:
        """
        Get subtopics that haven't been generated yet and meet criteria.

        PARAMETERS:
            min_score: Minimum SMB relevance score
            min_articles: Minimum number of source articles

        RETURNS:
            List of topic dictionaries for ungenerated subtopics
        """
        cursor = self.conn.execute("""
            SELECT
                t.*,
                COUNT(at.article_id) as article_count
            FROM topics t
            LEFT JOIN article_topics at ON t.id = at.topic_id
            WHERE t.is_parent = 0
                AND t.smb_relevance_score >= ?
                AND t.id NOT IN (SELECT topic_id FROM generated_articles)
            GROUP BY t.id
            HAVING COUNT(at.article_id) >= ?
            ORDER BY COUNT(at.article_id) DESC
        """, (min_score, min_articles))

        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def close(self):
        """Close database connection."""
        self.conn.close()
        logger.info("Database connection closed")


# ============================================================================
# TEST CODE
# This runs when you execute: python database.py
# ============================================================================
if __name__ == '__main__':
    """
    Test suite for database module.

    WHAT THIS DOES:
    - Creates a test database (separate from production)
    - Tests all major functionality
    - Cleans up test database when done

    RUN THIS:
    python database.py

    EXPECTED OUTPUT:
    Testing database module...
    1. Testing article insertion...
       Inserted article with ID: 1
    2. Testing duplicate prevention...
       Duplicate insert returned: None (should be None)
    ...
    ✓ All database tests passed!
    """
    print("Testing database module...")

    # Create test database (separate from production data)
    db = Database('data/test_pipeline.db')

    # ============ TEST 1: Article insertion ============
    print("\n1. Testing article insertion...")
    test_article = {
        'url': 'https://test.com/article1',
        'title': 'Test Article',
        'content': 'This is test content',
        'source': 'Test Source',
        'fetched_date': datetime.now().isoformat()
    }

    article_id = db.insert_article(test_article)
    print(f"   Inserted article with ID: {article_id}")

    # ============ TEST 2: Duplicate prevention ============
    print("\n2. Testing duplicate prevention...")
    duplicate_id = db.insert_article(test_article)
    print(f"   Duplicate insert returned: {duplicate_id} (should be None)")

    # ============ TEST 3: Batch insertion ============
    print("\n3. Testing batch insertion...")
    batch_articles = [
        {
            'url': 'https://test.com/article2',
            'title': 'Article 2',
            'source': 'Test Source',
            'fetched_date': datetime.now().isoformat()
        },
        {
            'url': 'https://test.com/article3',
            'title': 'Article 3',
            'source': 'Test Source',
            'fetched_date': datetime.now().isoformat()
        },
        {
            'url': 'https://test.com/article1',  # Duplicate
            'title': 'Article 1 Duplicate',
            'source': 'Test Source',
            'fetched_date': datetime.now().isoformat()
        }
    ]

    inserted, skipped = db.insert_articles_batch(batch_articles)
    print(f"   Batch insert: {inserted} inserted, {skipped} skipped")

    # ============ TEST 4: Topic operations ============
    print("\n4. Testing topic operations...")
    topic_id = db.find_or_create_topic(
        topic_name="Test v. Example - Contract Dispute",
        category="contract law",
        key_entity="Test v. Example",
        smb_relevance_score=8
    )
    print(f"   Created/found topic with ID: {topic_id}")

    # ============ TEST 5: Linking ============
    print("\n5. Testing article-topic linking...")
    db.link_article_to_topic(article_id, topic_id)
    print(f"   Linked article {article_id} to topic {topic_id}")

    # ============ TEST 6: Retrieval ============
    print("\n6. Testing data retrieval...")
    articles_for_topic = db.get_articles_for_topic(topic_id)
    print(f"   Found {len(articles_for_topic)} articles for topic {topic_id}")

    # ============ TEST 7: Stats ============
    print("\n7. Database statistics:")
    stats = db.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # Cleanup
    db.close()
    os.remove('data/test_pipeline.db')

    print("\n✓ All database tests passed!")
