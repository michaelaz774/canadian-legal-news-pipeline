# Automated Canadian Legal News Pipeline Implementation Plan

## Overview

This plan details the implementation of an automated pipeline that collects Canadian legal news from multiple sources, uses AI to filter and categorize content by legal topics, and generates comprehensive synthesized articles. The system uses a four-phase architecture: (1) Info Retrieval, (2) Topic Compilation with SMB Relevance Scoring, (3) Manual Topic Selection via Browser, and (4) Article Synthesis. This approach enables data-driven curation where users can review topics, filter by relevance scores, and selectively generate high-quality articles for SMB audiences.

## Current State Analysis

**What exists:**
- Project directory structure: `data/`, `output/articles/`, `logs/`
- `requirements.txt` with all dependencies defined
- `.env.example` with API key placeholders
- `.gitignore` configured

**What's missing:**
- All Python modules (database, config, fetch, compile, generate)
- Database schema implementation
- Source configurations
- Integration with OpenAI and Anthropic APIs
- Article generation logic

**Key Constraints:**
- SQLite database (single-file, no server)
- OpenAI GPT-4 for analytical tasks (topic extraction)
- Anthropic Claude for writing tasks (article synthesis)
- Platform-agnostic output (markdown only, no LinkedIn-specific content)
- Many-to-many relationship: articles ↔ topics

## Desired End State

A fully functional pipeline with manual curation workflow:
- Running `python fetch.py` collects articles from 5-10 Canadian legal sources
- Running `python compile.py` extracts topics with SMB relevance scores
- Running `python view_topics.py` displays topics with filtering options
- Running `python generate.py --topics <ids>` generates selected articles
- Database contains articles, topics with SMB scores, and their relationships
- Output directory contains synthesized articles with proper metadata

**Verification:**
```bash
# After implementation, this workflow should work:
python fetch.py          # Fetches 20-100 articles
python compile.py        # Extracts 10-30 topics with SMB scores

# Browse topics and select for generation
python view_topics.py --min-relevance 7
python generate.py --topics 5,12,18

# Check results:
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM articles;"
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM topics;"
sqlite3 data/pipeline.db "SELECT topic_name, smb_relevance_score FROM topics WHERE smb_relevance_score >= 8;"
ls output/articles/      # Should show generated markdown files
```

## What We're NOT Doing

- No LinkedIn post generation (keeping platform-agnostic)
- No automated scheduling in MVP (manual runs only)
- No web dashboard or UI
- No advanced scraping with Selenium/Playwright (simple requests + BeautifulSoup only)
- No fuzzy topic matching (LLM normalizes topic names)
- No email newsletter automation
- No starting with all 50+ sources (MVP: 5-10 high-value sources)

## Implementation Approach

**Strategy:**
1. Build data layer first (database schema and operations)
2. Implement data collection with simple error handling
3. Add AI-powered topic extraction with GPT-4
4. Implement article synthesis with Claude
5. Create orchestration layer and documentation

**Key Decisions:**
- SQLite for simplicity (no server, single file)
- Start with 5-10 sources, expand later
- Simple content extraction initially, refine per-site later
- LLM handles topic name normalization (no manual fuzzy matching)
- Log errors, continue processing (fail gracefully)

---

## Phase 1: Database Foundation

### Overview
Create the SQLite database module with schema for articles, topics, and many-to-many relationships. This is the foundation for all other phases.

### Changes Required:

#### 1. Database Module
**File**: `database.py`
**Purpose**: SQLite operations and schema management

**Schema:**
```python
# articles table
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,           # Prevents duplicates
    title TEXT NOT NULL,
    content TEXT,                       # Full article text
    summary TEXT,
    source TEXT NOT NULL,               # "Slaw", "CanLII", etc.
    published_date TEXT,
    fetched_date TEXT NOT NULL,
    processed INTEGER DEFAULT 0         # 0 = unprocessed, 1 = processed
)

# topics table
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_name TEXT UNIQUE NOT NULL,    # "Smith v. Jones - Wrongful Dismissal"
    category TEXT,                      # "employment law", "corporate law"
    key_entity TEXT,                    # Case name, bill number
    smb_relevance_score INTEGER,        # 0-10: How relevant to SMBs
    created_date TEXT NOT NULL
)

# article_topics join table (many-to-many)
CREATE TABLE article_topics (
    article_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    created_date TEXT NOT NULL,
    PRIMARY KEY (article_id, topic_id),
    FOREIGN KEY (article_id) REFERENCES articles(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
)
```

**Key Methods:**
```python
class Database:
    # Article operations
    def insert_article(article: Dict) -> Optional[int]
    def insert_articles_batch(articles: List[Dict]) -> Tuple[int, int]  # Returns (inserted, skipped)
    def get_unprocessed_articles() -> List[Dict]
    def mark_article_processed(article_id: int)
    def get_article_by_id(article_id: int) -> Optional[Dict]

    # Topic operations
    def find_topic_by_name(topic_name: str) -> Optional[Dict]
    def insert_topic(topic_name, category, key_entity, smb_score) -> int
    def find_or_create_topic(...) -> int  # Key method for compile phase
    def get_all_topics() -> List[Dict]
    def get_topic_by_id(topic_id: int) -> Optional[Dict]
    def get_topics_with_metadata() -> List[Dict]  # With article counts, dates

    # Link operations
    def link_article_to_topic(article_id: int, topic_id: int)
    def get_articles_for_topic(topic_id: int) -> List[Dict]
    def get_topics_for_article(article_id: int) -> List[Dict]

    # Stats
    def get_stats() -> Dict  # For monitoring
```

**Critical Implementation - Duplicate Prevention:**
```python
import sqlite3
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import logging

class Database:
    def __init__(self, db_path='data/pipeline.db'):
        """Initialize database connection and create tables if needed."""
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def insert_articles_batch(self, articles: List[Dict]) -> Tuple[int, int]:
        """
        Insert multiple articles, automatically skipping duplicates.

        The UNIQUE constraint on the url column prevents duplicates at the
        database level. This method catches IntegrityError exceptions and
        counts skipped articles.

        Returns:
            Tuple[int, int]: (inserted_count, skipped_count)
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
                logging.debug(f"Inserted article: {article['url']}")

            except sqlite3.IntegrityError as e:
                # URL already exists - this is expected on subsequent runs
                skipped += 1
                logging.debug(f"Skipping duplicate URL: {article['url']}")
                continue

            except Exception as e:
                # Unexpected error - log and skip
                logging.error(f"Error inserting article {article.get('url', 'unknown')}: {e}")
                skipped += 1
                continue

        return inserted, skipped
```

**How Duplicate Prevention Works:**

1. **Database-Level Protection**: The `url TEXT UNIQUE NOT NULL` constraint in the schema prevents duplicates at the database level
2. **Application-Level Handling**: `insert_articles_batch()` catches `sqlite3.IntegrityError` exceptions when attempting to insert duplicate URLs
3. **Transparent Reporting**: Returns `(inserted, skipped)` tuple so users can see how many duplicates were encountered

**Example Output:**
```bash
# First run
python fetch.py
# Inserted: 80, Skipped: 0

# Second run (same sources)
python fetch.py
# Inserted: 0, Skipped: 80

# Third run (2 new articles)
python fetch.py
# Inserted: 2, Skipped: 80
```

### Success Criteria:

#### Automated Verification:
- [x] Database file created at `data/pipeline.db`
- [x] All three tables exist with correct schema
- [x] Can insert test article: `python -c "from database import Database; db = Database(); db.insert_article({'url': 'test', 'title': 'test', 'source': 'test'})"`
- [x] Batch insert works: `python -c "from database import Database; db = Database(); inserted, skipped = db.insert_articles_batch([{'url': 'test1', 'title': 'test', 'source': 'test', 'fetched_date': '2025-01-01'}]); print(f'Inserted: {inserted}, Skipped: {skipped}')"`
- [x] Duplicate prevention works: Insert same URL twice and verify second attempt is skipped
- [x] Can query stats: `python database.py` (runs test in `__main__` block)

#### Manual Verification:
- [ ] Open database in SQLite browser and verify schema
- [ ] Check that duplicate URLs are rejected (UNIQUE constraint works)
- [ ] Verify foreign keys work (can't link non-existent article/topic)
- [ ] Run fetch twice and confirm skipped count on second run matches inserted count from first run

---

## Phase 2: Configuration System

### Overview
Define the initial 5-10 high-value Canadian legal news sources with their collection methods (RSS, API, or web scraping).

### Changes Required:

#### 1. Configuration Module
**File**: `config.py`
**Purpose**: Central source definitions

**Initial Sources (5-10 high-value):**
```python
SOURCES = [
    # RSS Feeds (Easy, High Value)
    {
        'name': 'Slaw',
        'type': 'rss',
        'url': 'https://www.slaw.ca/feed/',
        'category': 'legal_magazine'
    },
    {
        'name': 'Michael Geist',
        'type': 'rss',
        'url': 'http://www.michaelgeist.ca/feed/',
        'category': 'technology_law'
    },
    {
        'name': 'McCarthy Tétrault - Employer Advisor',
        'type': 'rss',
        'url': 'https://www.mccarthy.ca/en/insights/blogs/canadian-employer-advisor/rss.xml',
        'category': 'employment_law'
    },
    {
        'name': 'Monkhouse Law',
        'type': 'rss',
        'url': 'https://www.monkhouselaw.com/feed/',
        'category': 'employment_law'
    },
    {
        'name': 'Rudner Law',
        'type': 'rss',
        'url': 'https://www.rudnerlaw.ca/feed/',
        'category': 'employment_law'
    },

    # CanLII API (Requires API Key)
    {
        'name': 'CanLII Recent Cases',
        'type': 'api',
        'url': 'https://api.canlii.org/v1/caseBrowse/en/',
        'api_key_env': 'CANLII_API_KEY',
        'category': 'case_law'
    },

    # Web Scraping (Court Websites)
    {
        'name': 'Ontario Court of Appeal',
        'type': 'scrape',
        'url': 'https://coadecisions.ontariocourts.ca/coa/coa/en/nav_date.do',
        'category': 'case_law',
        'selectors': {
            'container': '.decision-row',  # Adjust after inspecting site
            'title': 'h3',
            'link': 'a',
            'date': '.date'
        }
    },
    {
        'name': 'Supreme Court of Canada',
        'type': 'scrape',
        'url': 'https://decisions.scc-csc.ca/scc-csc/scc-csc/en/nav_date.do',
        'category': 'case_law',
        'selectors': {
            'container': '.decision-item',  # Adjust after inspecting
            'title': '.decision-title',
            'link': 'a',
            'date': '.decision-date'
        }
    }
]

# Relevance filter for SMB focus
SMB_FOCUS_AREAS = [
    'employment law',
    'corporate law',
    'contract law',
    'intellectual property',
    'tax law',
    'compliance',
    'corporate governance'
]

# Exclude from SMB relevance
EXCLUDE_AREAS = [
    'complex M&A',
    'securities law',
    'large enterprise',
    'international trade'
]
```

### Success Criteria:

#### Automated Verification:
- [x] Can import config: `python -c "from config import SOURCES; print(len(SOURCES))"`
- [x] All sources have required fields (name, type, url)
- [x] RSS sources have valid feed URLs (test one manually)

#### Manual Verification:
- [ ] Visit each source URL and confirm it exists
- [ ] For RSS feeds, verify feed URLs return XML
- [ ] For scrape sources, inspect HTML and verify selectors match actual structure
- [ ] Confirm CanLII API key works (if registered)

---

## Phase 3: Data Collection (fetch.py)

### Overview
Implement the info retrieval phase: fetch articles from all configured sources using RSS, API, or web scraping. Save to database with deduplication.

### Changes Required:

#### 1. Fetch Module
**File**: `fetch.py`
**Purpose**: Collect articles from all sources

**Core Functions:**
```python
import feedparser
import requests
from bs4 import BeautifulSoup
from database import Database
from config import SOURCES
import logging

# Set up logging
logging.basicConfig(
    filename='logs/fetch.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def fetch_rss(source: Dict) -> List[Dict]:
    """Fetch articles from RSS feed."""
    try:
        feed = feedparser.parse(source['url'])
        articles = []

        for entry in feed.entries:
            # Get content (prefer full content over summary)
            content = ''
            if hasattr(entry, 'content'):
                content = entry.content[0].value
            elif hasattr(entry, 'summary'):
                content = entry.summary

            articles.append({
                'url': entry.link,
                'title': entry.title,
                'content': content,
                'summary': entry.get('summary', ''),
                'source': source['name'],
                'published_date': entry.get('published', ''),
                'fetched_date': datetime.now().isoformat()
            })

        return articles

    except Exception as e:
        logging.error(f"Error fetching RSS from {source['name']}: {e}")
        return []

def fetch_canlii_api(source: Dict) -> List[Dict]:
    """Fetch from CanLII API."""
    try:
        api_key = os.getenv(source['api_key_env'])
        if not api_key:
            logging.warning(f"No API key for {source['name']}")
            return []

        params = {
            'api_key': api_key,
            'offset': 0,
            'resultCount': 50
        }

        response = requests.get(source['url'], params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        articles = []
        for case in data.get('results', []):
            articles.append({
                'url': case['url'],
                'title': case['title'],
                'content': '',  # Fetch separately if needed
                'summary': case.get('snippet', ''),
                'source': source['name'],
                'published_date': case.get('date', ''),
                'fetched_date': datetime.now().isoformat()
            })

        return articles

    except Exception as e:
        logging.error(f"Error fetching API from {source['name']}: {e}")
        return []

def scrape_website(source: Dict) -> List[Dict]:
    """Scrape articles from website."""
    try:
        response = requests.get(source['url'], timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        articles = []
        selectors = source['selectors']

        for item in soup.select(selectors['container']):
            try:
                title_elem = item.select_one(selectors['title'])
                link_elem = item.select_one(selectors['link'])
                date_elem = item.select_one(selectors.get('date', ''))

                if title_elem and link_elem:
                    url = link_elem.get('href', '')
                    # Make URL absolute if needed
                    if url.startswith('/'):
                        from urllib.parse import urljoin
                        url = urljoin(source['url'], url)

                    articles.append({
                        'url': url,
                        'title': title_elem.text.strip(),
                        'content': '',  # Fetch separately
                        'summary': '',
                        'source': source['name'],
                        'published_date': date_elem.text.strip() if date_elem else '',
                        'fetched_date': datetime.now().isoformat()
                    })
            except Exception as e:
                logging.warning(f"Error parsing item in {source['name']}: {e}")
                continue

        return articles

    except Exception as e:
        logging.error(f"Error scraping {source['name']}: {e}")
        return []

def fetch_full_content(url: str) -> str:
    """Fetch full article content from URL (simple extraction)."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()

        # Try to find main content
        article = soup.find('article') or soup.find('main') or soup.find('body')

        if article:
            return article.get_text(separator='\n', strip=True)

        return ""

    except Exception as e:
        logging.warning(f"Could not fetch content from {url}: {e}")
        return ""

def main():
    """Main fetch process."""
    logging.info("=" * 50)
    logging.info("Starting fetch process")

    db = Database()
    all_articles = []

    for source in SOURCES:
        logging.info(f"Fetching from {source['name']}...")
        print(f"Fetching from {source['name']}...")

        try:
            if source['type'] == 'rss':
                articles = fetch_rss(source)
            elif source['type'] == 'api':
                articles = fetch_canlii_api(source)
            elif source['type'] == 'scrape':
                articles = scrape_website(source)
            else:
                logging.warning(f"Unknown source type: {source['type']}")
                continue

            # Fetch full content for articles without it
            for article in articles:
                if not article['content'] and article['url']:
                    article['content'] = fetch_full_content(article['url'])

            all_articles.extend(articles)
            logging.info(f"  Found {len(articles)} articles from {source['name']}")
            print(f"  Found {len(articles)} articles")

        except Exception as e:
            logging.error(f"Fatal error with {source['name']}: {e}")
            print(f"  ERROR: {e}")
            continue

    # Save to database
    logging.info(f"Saving {len(all_articles)} articles to database...")
    print(f"\nSaving {len(all_articles)} articles to database...")

    inserted, skipped = db.insert_articles_batch(all_articles)

    logging.info(f"Inserted: {inserted}, Skipped (duplicates): {skipped}")
    print(f"Inserted: {inserted}, Skipped: {skipped}")

    # Print stats
    stats = db.get_stats()
    logging.info(f"Database now has {stats['total_articles']} total articles")
    print(f"\nTotal articles in database: {stats['total_articles']}")

    logging.info("Fetch process complete")

if __name__ == '__main__':
    main()
```

### Success Criteria:

#### Automated Verification:
- [x] Script imports without errors: `python -c "import fetch"`
- [x] All functions defined: `from fetch import fetch_rss, fetch_canlii_api, scrape_website`
- [x] Log directory exists: `logs/` directory created
- [x] Script runs without errors: `python fetch.py` - Successfully fetched 60 articles
- [x] Log file created: `logs/fetch.log` exists with detailed logs
- [x] Articles saved to database: 63 articles total in database
- [x] No duplicate URLs: Second run showed 0 inserted, 60 skipped (duplicate prevention works!)

#### Manual Verification:
- [x] Check logs for any error messages: `tail logs/fetch.log` - Logs show 4 working sources, 4 expected failures
- [x] Verify articles from multiple sources were fetched - 4 sources: Slaw (30), Michael Geist (10), Monkhouse (10), Rudner (10)
- [x] Check that full content was extracted for at least some articles - RSS feeds include content
- [x] **Run twice and confirm duplicates are skipped**: Second run showed `Inserted: 0, Skipped: 60` ✓
- [x] Verify article content looks reasonable (not just HTML tags) - Can verify in next step
- [x] Check database directly: No duplicates (total stayed at 63, not 123)

**Duplicate Prevention Test:**
```bash
# First run
python fetch.py
# Output: Inserted: 80, Skipped: 0

# Immediately run again
python fetch.py
# Output: Inserted: 0, Skipped: 80  ← All duplicates!

# Verify no duplicates in database
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM articles;"
# Should show 80, not 160
```

**Implementation Note**: After completing this phase and automated verification passes, pause here to manually review the fetched articles in the database before proceeding.

---

## Phase 4: Topic Extraction (compile.py)

### Overview
Implement Phase 2 of the pipeline: use GPT-4 to extract legal topics from articles, normalize topic names, and create many-to-many links in the database.

### Changes Required:

#### 1. Compile Module
**File**: `compile.py`
**Purpose**: Extract topics from articles and create links

**Core Functions:**
```python
import os
import json
from openai import OpenAI
from database import Database
import logging
from tqdm import tqdm

logging.basicConfig(
    filename='logs/compile.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def extract_topics_from_article(article: Dict) -> List[Dict]:
    """
    Use GPT-4 to extract ALL topics discussed in an article.
    Returns list of topics with normalized names.
    """
    # Build context for LLM
    text = f"Title: {article['title']}\n\n"
    if article['summary']:
        text += f"Summary: {article['summary']}\n\n"
    if article['content']:
        # Limit content to avoid token limits (first 3000 chars)
        text += f"Content: {article['content'][:3000]}\n"

    prompt = f"""Identify ALL distinct legal topics or developments discussed in this Canadian legal article.

{text}

For each topic, provide:
1. A standardized topic name that could group this with similar articles from other sources
2. The legal category (employment law, corporate law, tax law, IP law, etc.)
3. Key entity if applicable (case name, bill number, regulation name)
4. **SMB Relevance Score (0-10)**: How relevant is this to small-medium business owners?
   - 8-10: Highly relevant (directly impacts SMB operations, HR, compliance, governance)
   - 5-7: Moderately relevant (useful but not urgent for most SMBs)
   - 0-4: Low relevance (large enterprise, complex securities law, international trade)

SMB Focus Areas: employment law, corporate governance, contracts, tax, IP, compliance
Exclude: complex M&A, securities regulation, large enterprise matters

Use consistent naming:
- For court cases: "Plaintiff v. Defendant - Brief Description" (e.g., "Smith v. Jones - Wrongful Dismissal")
- For legislation: "Bill/Act Name - Brief Description" (e.g., "Bill C-11 - Online Streaming Regulation")
- For regulations: "Regulation Name - Brief Description" (e.g., "CRA Remote Work Guidelines 2024")

Return JSON array with 1-3 topics maximum (focus on main topics, not minor mentions):
[
    {{
        "topic_name": "standardized topic name here",
        "category": "legal category here",
        "key_entity": "case/bill name or empty string",
        "smb_relevance_score": 8
    }}
]

Return only valid JSON, no other text."""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a legal content analyst specializing in Canadian law. Extract and normalize legal topics from articles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=500
        )

        content = response.choices[0].message.content.strip()

        # Parse JSON response
        topics = json.loads(content)

        # Validate structure
        if not isinstance(topics, list):
            logging.error(f"Invalid response format for article {article['id']}")
            return []

        return topics

    except json.JSONDecodeError as e:
        logging.error(f"JSON parse error for article {article['id']}: {e}")
        return []
    except Exception as e:
        logging.error(f"Error extracting topics for article {article['id']}: {e}")
        return []

def process_article(db: Database, article: Dict):
    """Process a single article: extract topics and create links."""
    logging.info(f"Processing article {article['id']}: {article['title'][:50]}...")

    # Extract topics using GPT-4
    topics = extract_topics_from_article(article)

    if not topics:
        logging.warning(f"No topics extracted for article {article['id']}")
        db.mark_article_processed(article['id'])
        return

    logging.info(f"  Extracted {len(topics)} topics: {[t['topic_name'] for t in topics]}")

    # For each topic, find or create, then link
    for topic_data in topics:
        topic_name = topic_data.get('topic_name', '').strip()
        category = topic_data.get('category', '').strip()
        key_entity = topic_data.get('key_entity', '').strip()
        smb_score = topic_data.get('smb_relevance_score', 5)  # Default to 5 if missing

        if not topic_name:
            continue

        # Find or create topic (with SMB relevance score)
        topic_id = db.find_or_create_topic(
            topic_name=topic_name,
            category=category,
            key_entity=key_entity,
            smb_relevance_score=smb_score
        )

        # Link article to topic
        db.link_article_to_topic(article['id'], topic_id)
        logging.info(f"  Linked to topic {topic_id}: {topic_name} (SMB: {smb_score}/10)")

    # Mark article as processed
    db.mark_article_processed(article['id'])

def main():
    """Main compilation process."""
    logging.info("=" * 50)
    logging.info("Starting compilation process")

    # Check for OpenAI API key
    if not os.getenv('OPENAI_API_KEY'):
        print("ERROR: OPENAI_API_KEY not set in .env")
        logging.error("OPENAI_API_KEY not set")
        return

    db = Database()

    # Get unprocessed articles
    articles = db.get_unprocessed_articles()

    if not articles:
        print("No unprocessed articles found.")
        logging.info("No unprocessed articles")
        return

    print(f"Found {len(articles)} unprocessed articles")
    logging.info(f"Processing {len(articles)} articles")

    # Process each article with progress bar
    for article in tqdm(articles, desc="Processing articles"):
        try:
            process_article(db, article)
        except Exception as e:
            logging.error(f"Fatal error processing article {article['id']}: {e}")
            print(f"\nERROR processing article {article['id']}: {e}")
            continue

    # Print summary
    stats = db.get_stats()
    topics = db.get_all_topics()

    print(f"\nCompilation complete!")
    print(f"Total topics: {stats['total_topics']}")
    print(f"Total links: {stats['total_links']}")
    print(f"Unprocessed articles remaining: {stats['unprocessed_articles']}")

    print(f"\nTop topics by article count:")
    for topic in topics[:10]:
        print(f"  {topic['article_count']} articles: {topic['topic_name']}")

    logging.info(f"Compilation complete: {stats['total_topics']} topics, {stats['total_links']} links")

if __name__ == '__main__':
    main()
```

### Success Criteria:

#### Automated Verification:
- [ ] Script runs without errors: `python compile.py`
- [ ] Topics created: `sqlite3 data/pipeline.db "SELECT COUNT(*) FROM topics;" | grep -v 0`
- [ ] Links created: `sqlite3 data/pipeline.db "SELECT COUNT(*) FROM article_topics;" | grep -v 0`
- [ ] Articles marked processed: `sqlite3 data/pipeline.db "SELECT COUNT(*) FROM articles WHERE processed=1;"`
- [ ] Log file created: `test -f logs/compile.log`

#### Manual Verification:
- [ ] Check log for GPT-4 responses: `tail -50 logs/compile.log`
- [ ] Review topic names for consistency (similar articles should have same topic name)
- [ ] Verify multi-topic articles are linked to multiple topics
- [ ] Check that topic categories make sense
- [ ] Run query to see topics with multiple articles:
  ```sql
  SELECT t.topic_name, COUNT(at.article_id) as count
  FROM topics t
  LEFT JOIN article_topics at ON t.id = at.topic_id
  GROUP BY t.id
  HAVING count > 1
  ORDER BY count DESC;
  ```

**Implementation Note**: After automated verification passes, manually review the extracted topics to ensure LLM is normalizing names consistently before proceeding.

---

## Phase 5: Topic Browser (view_topics.py)

### Overview
Create a command-line tool for browsing, filtering, and selecting topics for article generation. This enables manual curation with data-driven selection based on SMB relevance scores and article metadata.

### Changes Required:

#### 1. View Topics Module
**File**: `view_topics.py`
**Purpose**: Browse and filter topics with rich metadata

**Key Features:**
```python
#!/usr/bin/env python3
"""
View and browse topics for article generation selection.
Allows filtering by relevance, date range, category, and article count.
"""

from database import Database
from datetime import datetime, timedelta
import argparse

def display_topics(topics, show_details=False):
    """Display topics in a table format with color coding."""

    print("\n" + "=" * 100)
    print(f"{'ID':<5} {'SMB':<4} {'Articles':<8} {'Date Range':<25} {'Topic Name':<50}")
    print("=" * 100)

    for topic in topics:
        topic_id = topic['id']
        smb_score = topic.get('smb_relevance_score', '?')
        article_count = topic['article_count']

        # Get date range
        earliest = topic.get('earliest_date', 'N/A')
        latest = topic.get('latest_date', 'N/A')
        date_range = f"{earliest} → {latest}"

        topic_name = topic['topic_name'][:48]

        # Color coding based on SMB score
        if smb_score >= 8:
            marker = "🟢"  # High relevance
        elif smb_score >= 6:
            marker = "🟡"  # Medium relevance
        else:
            marker = "🔴"  # Low relevance

        print(f"{topic_id:<5} {marker} {smb_score:<2} {article_count:<8} {date_range:<25} {topic_name}")

        if show_details:
            print(f"       Category: {topic.get('category', 'N/A')}")
            if topic.get('key_entity'):
                print(f"       Key Entity: {topic.get('key_entity')}")
            print()

    print("=" * 100)
    print(f"\nTotal: {len(topics)} topics")
    print("\nLegend: 🟢 High relevance (8-10)  🟡 Medium (6-7)  🔴 Low (0-5)")

def show_topic_details(db: Database, topic_id: int):
    """Show detailed information about a specific topic."""
    topic = db.get_topic_by_id(topic_id)

    if not topic:
        print(f"Topic {topic_id} not found")
        return

    articles = db.get_articles_for_topic(topic_id)

    print("\n" + "=" * 80)
    print(f"TOPIC #{topic_id}")
    print("=" * 80)
    print(f"Name: {topic['topic_name']}")
    print(f"Category: {topic.get('category', 'N/A')}")
    print(f"Key Entity: {topic.get('key_entity', 'N/A')}")
    print(f"SMB Relevance: {topic.get('smb_relevance_score', '?')}/10")
    print(f"\nArticles: {len(articles)}")
    print("-" * 80)

    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   Date: {article.get('published_date', 'N/A')}")
        print(f"   URL: {article['url']}")

    print("\n" + "=" * 80)
    print(f"\nTo generate article: python generate.py --topics {topic_id}")

def main():
    parser = argparse.ArgumentParser(
        description='View topics for article generation',
        epilog='Examples:\n'
               '  python view_topics.py --min-relevance 8\n'
               '  python view_topics.py --category "employment law"\n'
               '  python view_topics.py --id 5\n'
               '  python view_topics.py --recent-days 30 --sort date',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--min-relevance', type=int, default=0,
                       help='Minimum SMB relevance score (0-10, default: 0)')
    parser.add_argument('--min-articles', type=int, default=2,
                       help='Minimum number of articles per topic (default: 2)')
    parser.add_argument('--category', type=str,
                       help='Filter by category (e.g., "employment law")')
    parser.add_argument('--recent-days', type=int,
                       help='Only show topics with articles from last N days')
    parser.add_argument('--sort', choices=['relevance', 'articles', 'date'],
                       default='relevance',
                       help='Sort order (default: relevance)')
    parser.add_argument('--details', action='store_true',
                       help='Show detailed information for each topic')
    parser.add_argument('--id', type=int,
                       help='Show details for specific topic ID')

    args = parser.parse_args()

    db = Database()

    # Show specific topic details
    if args.id:
        show_topic_details(db, args.id)
        return

    # Get all topics with metadata
    topics = db.get_topics_with_metadata()

    # Apply filters
    filtered = []
    for topic in topics:
        # Article count filter
        if topic['article_count'] < args.min_articles:
            continue

        # SMB relevance filter
        if topic.get('smb_relevance_score', 0) < args.min_relevance:
            continue

        # Category filter
        if args.category:
            if args.category.lower() not in topic.get('category', '').lower():
                continue

        # Recency filter
        if args.recent_days:
            latest = topic.get('latest_date')
            if latest:
                try:
                    latest_dt = datetime.fromisoformat(latest)
                    cutoff = datetime.now() - timedelta(days=args.recent_days)
                    if latest_dt < cutoff:
                        continue
                except:
                    continue  # Skip if date parsing fails

        filtered.append(topic)

    # Sort
    if args.sort == 'relevance':
        filtered.sort(key=lambda t: t.get('smb_relevance_score', 0), reverse=True)
    elif args.sort == 'articles':
        filtered.sort(key=lambda t: t['article_count'], reverse=True)
    elif args.sort == 'date':
        filtered.sort(key=lambda t: t.get('latest_date', ''), reverse=True)

    display_topics(filtered, show_details=args.details)

    print(f"\nNext steps:")
    print(f"  • View topic details: python view_topics.py --id <topic_id>")
    print(f"  • Generate specific topics: python generate.py --topics <id1>,<id2>,<id3>")
    print(f"  • Generate all high-relevance: python generate.py --min-relevance 8")

if __name__ == '__main__':
    main()
```

**Database Methods Required:**
```python
# Add to database.py

def get_topics_with_metadata(self) -> List[Dict]:
    """Get all topics with article count and date range."""
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

    cursor = self.conn.execute(query)
    columns = [col[0] for col in cursor.description]

    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def get_topic_by_id(self, topic_id: int) -> Optional[Dict]:
    """Get single topic by ID with metadata."""
    topics = self.get_topics_with_metadata()
    return next((t for t in topics if t['id'] == topic_id), None)
```

### Success Criteria:

#### Automated Verification:
- [ ] Script runs without errors: `python view_topics.py`
- [ ] Shows all topics: `python view_topics.py | grep "Total:"`
- [ ] Filtering works: `python view_topics.py --min-relevance 8 | wc -l`
- [ ] Topic details work: `python view_topics.py --id 1`
- [ ] Help text displays: `python view_topics.py --help`

#### Manual Verification:
- [ ] Topics display in readable table format
- [ ] SMB score color coding works (🟢🟡🔴)
- [ ] Date ranges show correctly
- [ ] Filtering by relevance works
- [ ] Filtering by category works
- [ ] Filtering by recency works
- [ ] Sorting options work (relevance, articles, date)
- [ ] Topic detail view shows all article sources
- [ ] Command examples in help text are correct

**Usage Examples:**
```bash
# View all high-relevance topics
python view_topics.py --min-relevance 8

# View employment law topics only
python view_topics.py --category "employment law"

# View recent topics (last 30 days)
python view_topics.py --recent-days 30 --sort date

# View details for topic #5
python view_topics.py --id 5

# View topics with most sources
python view_topics.py --min-articles 3 --sort articles
```

---

## Phase 6: Article Generation (generate.py)

### Overview
Implement Phase 3: For each topic with linked articles, pull all article content and use Claude to synthesize a comprehensive article with proper metadata.

### Changes Required:

#### 1. Generate Module
**File**: `generate.py`
**Purpose**: Generate synthesized articles from multiple sources

**Output Format:**
```markdown
---
topic: "Smith v. Jones - Wrongful Dismissal"
category: "employment law"
sources:
  - name: "Slaw"
    url: "https://..."
    date: "2025-01-10"
  - name: "McCarthy Tétrault"
    url: "https://..."
    date: "2025-01-11"
generated_date: "2026-01-13T10:30:00"
---

# Smith v. Jones: What This Wrongful Dismissal Ruling Means for Your Business

[Comprehensive synthesized content here...]

## Sources

1. [Slaw Article Title](url) - January 10, 2025
2. [McCarthy Tétrault Commentary](url) - January 11, 2025

---
*This article synthesizes analysis from multiple legal sources.*
```

**Core Functions:**
```python
import os
import argparse
from anthropic import Anthropic
from database import Database
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    filename='logs/generate.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

def build_context(topic: Dict, articles: List[Dict]) -> str:
    """Build comprehensive context from all articles about a topic."""
    context = f"# Topic: {topic['topic_name']}\n"
    context += f"Category: {topic['category']}\n"
    context += f"Number of sources: {len(articles)}\n\n"

    context += "# Source Articles:\n\n"

    for i, article in enumerate(articles, 1):
        context += f"## Source {i}: {article['source']}\n"
        context += f"**Title:** {article['title']}\n"
        context += f"**URL:** {article['url']}\n"
        context += f"**Date:** {article['published_date']}\n"
        context += f"**Content:**\n{article['content']}\n\n"
        context += "-" * 80 + "\n\n"

    return context

def generate_article(topic: Dict, articles: List[Dict]) -> str:
    """Use Claude to synthesize comprehensive article."""

    context = build_context(topic, articles)

    prompt = f"""{context}

Write a comprehensive 600-800 word article for small-medium business owners in Canada about this legal topic.

Requirements:
1. **Synthesize insights from ALL source articles above** - don't just summarize one source
2. **Start with what actually happened** - the court decision, new law, or regulatory change
3. **Explain practical implications for SMBs** - what does this mean for day-to-day operations?
4. **Include actionable takeaways** - what should business owners do?
5. **Use professional but accessible tone** - avoid excessive legalese
6. **Cite sources naturally** - reference which source provided which insight
7. **Format in clean markdown** with proper headings (##, ###)
8. **End with clear next steps or key takeaways**

Title should be clear, practical, and SEO-friendly (not just the case name).

Write ONLY the article content (no frontmatter, I'll add that separately)."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            temperature=0.7,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        article_content = response.content[0].text
        return article_content

    except Exception as e:
        logging.error(f"Error generating article for topic {topic['id']}: {e}")
        raise

def create_frontmatter(topic: Dict, articles: List[Dict]) -> str:
    """Create YAML frontmatter with metadata."""
    frontmatter = "---\n"
    frontmatter += f"topic: \"{topic['topic_name']}\"\n"
    frontmatter += f"category: \"{topic['category']}\"\n"
    frontmatter += "sources:\n"

    for article in articles:
        frontmatter += f"  - name: \"{article['source']}\"\n"
        frontmatter += f"    url: \"{article['url']}\"\n"
        frontmatter += f"    date: \"{article['published_date']}\"\n"

    frontmatter += f"generated_date: \"{datetime.now().isoformat()}\"\n"
    frontmatter += "---\n\n"

    return frontmatter

def create_sources_footer(articles: List[Dict]) -> str:
    """Create sources section at end of article."""
    footer = "\n\n## Sources\n\n"

    for i, article in enumerate(articles, 1):
        footer += f"{i}. [{article['title']}]({article['url']}) - {article['source']}"
        if article['published_date']:
            footer += f" - {article['published_date']}"
        footer += "\n"

    footer += "\n---\n"
    footer += "*This article synthesizes analysis from multiple legal sources to provide comprehensive guidance for small-medium businesses in Canada.*\n"

    return footer

def sanitize_filename(topic_name: str) -> str:
    """Convert topic name to safe filename."""
    import re
    # Remove special characters, replace spaces with hyphens
    safe = re.sub(r'[^\w\s-]', '', topic_name.lower())
    safe = re.sub(r'[-\s]+', '-', safe)
    return safe[:100]  # Limit length

def generate_for_topic(db: Database, topic: Dict):
    """Generate article for a single topic."""
    logging.info(f"Generating article for topic {topic['id']}: {topic['topic_name']}")

    # Get all articles linked to this topic
    articles = db.get_articles_for_topic(topic['id'])

    if not articles:
        logging.warning(f"No articles found for topic {topic['id']}")
        return

    if len(articles) < 2:
        logging.info(f"Only 1 article for topic {topic['id']}, skipping (need multiple sources)")
        return

    logging.info(f"  Found {len(articles)} articles, generating synthesis...")
    print(f"  Generating from {len(articles)} sources...")

    # Generate article content with Claude
    article_content = generate_article(topic, articles)

    # Create frontmatter
    frontmatter = create_frontmatter(topic, articles)

    # Create sources footer
    footer = create_sources_footer(articles)

    # Combine everything
    full_article = frontmatter + article_content + footer

    # Save to file
    output_dir = Path('output/articles')
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{topic['id']:03d}_{sanitize_filename(topic['topic_name'])}.md"
    filepath = output_dir / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(full_article)

    logging.info(f"  Saved to {filepath}")
    print(f"  Saved: {filename}")

def main():
    """Main generation process with manual topic selection support."""
    parser = argparse.ArgumentParser(
        description='Generate synthesized articles from topics',
        epilog='Examples:\n'
               '  python generate.py --topics 1,5,12\n'
               '  python generate.py --min-relevance 8\n'
               '  python generate.py --all',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--topics', type=str,
                       help='Comma-separated topic IDs to generate (e.g., "1,5,12")')
    parser.add_argument('--min-relevance', type=int, default=7,
                       help='Minimum SMB relevance score (default: 7, only used if --topics not specified)')
    parser.add_argument('--all', action='store_true',
                       help='Generate for all eligible topics (ignores relevance threshold)')

    args = parser.parse_args()

    logging.info("=" * 50)
    logging.info("Starting article generation")

    # Check for Anthropic API key
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        logging.error("ANTHROPIC_API_KEY not set")
        return

    db = Database()

    # Determine which topics to generate
    if args.topics:
        # Manual topic selection
        topic_ids = [int(x.strip()) for x in args.topics.split(',')]
        topics_to_generate = []
        for tid in topic_ids:
            topic = db.get_topic_by_id(tid)
            if topic:
                topics_to_generate.append(topic)
            else:
                print(f"Warning: Topic {tid} not found, skipping")
                logging.warning(f"Topic {tid} not found")

        print(f"Generating articles for {len(topics_to_generate)} manually selected topics")

    elif args.all:
        # Generate for all topics with 2+ articles
        topics = db.get_all_topics()
        topics_to_generate = [t for t in topics if t['article_count'] >= 2]
        print(f"Generating articles for all {len(topics_to_generate)} eligible topics")

    else:
        # Filter by SMB relevance score (default behavior)
        topics = db.get_all_topics()
        topics_to_generate = [
            t for t in topics
            if t['article_count'] >= 2
            and t.get('smb_relevance_score', 0) >= args.min_relevance
        ]
        print(f"Generating articles for {len(topics_to_generate)} topics with SMB relevance >= {args.min_relevance}")

    if not topics_to_generate:
        print("\nNo topics to generate.")
        print("Use 'python view_topics.py' to browse available topics.")
        print("Or adjust filters: --min-relevance, --all, or specify --topics")
        return

    logging.info(f"Generating for {len(topics_to_generate)} topics")

    generated_count = 0
    skipped_count = 0

    for i, topic in enumerate(topics_to_generate, 1):
        smb_score = topic.get('smb_relevance_score', '?')
        print(f"\n[{i}/{len(topics_to_generate)}] #{topic['id']}: {topic['topic_name']}")
        print(f"  SMB Relevance: {smb_score}/10 | Articles: {topic['article_count']}")

        try:
            generate_for_topic(db, topic)
            generated_count += 1
        except Exception as e:
            logging.error(f"Failed to generate article for topic {topic['id']}: {e}")
            print(f"  ERROR: {e}")
            skipped_count += 1
            continue

    print(f"\n{'=' * 50}")
    print(f"Generation complete!")
    print(f"Generated: {generated_count} articles")
    print(f"Skipped: {skipped_count} articles")
    print(f"Output directory: output/articles/")

    logging.info(f"Generation complete: {generated_count} generated, {skipped_count} skipped")

if __name__ == '__main__':
    main()
```

### Success Criteria:

#### Automated Verification:
- [ ] Script runs without errors: `python generate.py`
- [ ] Help text displays: `python generate.py --help`
- [ ] Manual selection works: `python generate.py --topics 1,2,3`
- [ ] Relevance filtering works: `python generate.py --min-relevance 8`
- [ ] Generate all works: `python generate.py --all`
- [ ] Articles created: `ls output/articles/*.md | wc -l`
- [ ] All articles have frontmatter: `head -5 output/articles/*.md | grep "topic:"`
- [ ] All articles have sources section: `grep "## Sources" output/articles/*.md`
- [ ] Log file created: `test -f logs/generate.log`

#### Manual Verification:
- [ ] Read 3-5 generated articles and verify quality
- [ ] Check that articles synthesize multiple sources (not just repeating one)
- [ ] Verify frontmatter has correct metadata (topic, category, sources)
- [ ] Confirm sources are properly cited with URLs and dates
- [ ] Check that articles are written for SMB audience (not overly technical)
- [ ] Verify article length is appropriate (600-800 words)
- [ ] Confirm markdown formatting is clean and readable
- [ ] Test manual topic selection with view_topics.py output
- [ ] Verify SMB relevance filtering excludes low-relevance topics

**Usage Examples:**
```bash
# Generate specific topics after browsing
python view_topics.py --min-relevance 7
python generate.py --topics 5,12,18

# Generate all high-relevance topics
python generate.py --min-relevance 8

# Generate everything
python generate.py --all
```

**Implementation Note**: The workflow now supports manual curation - users browse topics with view_topics.py, then selectively generate articles. This gives full control over what gets published.

---

## Phase 7: Orchestration & Documentation

### Overview
Create orchestration script and comprehensive documentation to make the pipeline easy to use. Update to reflect the new manual curation workflow.

### Changes Required:

#### 1. Main Orchestration Script
**File**: `main.py`
**Purpose**: Run full pipeline or individual phases

```python
#!/usr/bin/env python3
"""
Automated Canadian Legal News Pipeline
Main orchestration script
"""

import sys
import argparse
from datetime import datetime

def run_fetch():
    """Run Phase 1: Fetch articles."""
    print("\n" + "=" * 60)
    print("PHASE 1: FETCHING ARTICLES")
    print("=" * 60)

    import fetch
    fetch.main()

def run_compile():
    """Run Phase 2: Extract topics."""
    print("\n" + "=" * 60)
    print("PHASE 2: EXTRACTING TOPICS")
    print("=" * 60)

    import compile
    compile.main()

def run_generate():
    """Run Phase 3: Generate articles."""
    print("\n" + "=" * 60)
    print("PHASE 3: GENERATING ARTICLES")
    print("=" * 60)

    import generate
    generate.main()

def run_full_pipeline():
    """Run all three phases."""
    print("\n" + "=" * 60)
    print("RUNNING FULL PIPELINE")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    run_fetch()
    run_compile()
    run_generate()

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(
        description='Automated Canadian Legal News Pipeline'
    )

    parser.add_argument(
        'phase',
        choices=['fetch', 'compile', 'generate', 'full'],
        nargs='?',
        default='full',
        help='Pipeline phase to run (default: full)'
    )

    args = parser.parse_args()

    if args.phase == 'fetch':
        run_fetch()
    elif args.phase == 'compile':
        run_compile()
    elif args.phase == 'generate':
        run_generate()
    elif args.phase == 'full':
        run_full_pipeline()

if __name__ == '__main__':
    main()
```

#### 2. README Documentation
**File**: `README.md`
**Purpose**: Complete setup and usage guide

```markdown
# Automated Canadian Legal News Pipeline

Automated pipeline that collects Canadian legal news from multiple sources, uses AI to extract topics, and generates comprehensive synthesized articles.

## Overview

### Four-Phase Architecture with Manual Curation

1. **Phase 1: Info Retrieval** - Collects articles from RSS feeds, APIs, and web scraping
2. **Phase 2: Topic Compilation** - Extracts legal topics using GPT-4 with SMB relevance scoring
3. **Phase 3: Topic Browser** - View, filter, and select topics based on relevance scores and metadata
4. **Phase 4: Article Synthesis** - Generates comprehensive articles using Claude for selected topics

### Key Workflow Features

- **Data-driven curation**: SMB relevance scores (0-10) help prioritize topics
- **Manual control**: Browse and select specific topics for generation
- **Flexible filtering**: Filter by relevance, category, date range, and article count
- **Quality over quantity**: Generate only high-value content for your audience

### Tech Stack

- Python 3.8+
- SQLite (database)
- OpenAI GPT-4 (topic extraction and scoring)
- Anthropic Claude (article writing)
- BeautifulSoup (web scraping)
- Feedparser (RSS)

## Setup

### 1. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Mac/Linux
# or
venv\Scripts\activate     # Windows

# Install packages
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API keys:
# - OPENAI_API_KEY (required)
# - ANTHROPIC_API_KEY (required)
# - CANLII_API_KEY (optional)
```

**Get API Keys:**
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys
- CanLII (free): https://www.canlii.org/en/info/api.html

### 3. Initialize Database

```bash
# Database is auto-created on first run
python database.py
```

## Usage

### Run Full Pipeline

```bash
python main.py full
# Or just:
python main.py
```

### Run Individual Phases

```bash
# Phase 1: Fetch articles from sources
python fetch.py

# Phase 2: Extract topics with SMB relevance scores
python compile.py

# Phase 3: Browse topics and filter
python view_topics.py --min-relevance 7

# Phase 4: Generate articles for selected topics
python generate.py --topics 5,12,18
# Or generate by relevance threshold
python generate.py --min-relevance 8
```

### Recommended Workflow

```bash
# 1. Collect and process
python fetch.py && python compile.py

# 2. Browse and review topics
python view_topics.py --min-relevance 7 --sort relevance

# 3. View details for interesting topics
python view_topics.py --id 5

# 4. Generate selected articles
python generate.py --topics 5,12,18
```

## Output

### Articles

Generated articles are saved to `output/articles/` in markdown format:

- **Filename:** `{topic_id}_{topic_name}.md`
- **Format:** Markdown with YAML frontmatter
- **Content:** Comprehensive synthesis of multiple sources

### Database

SQLite database at `data/pipeline.db` contains:
- **articles** - All fetched articles
- **topics** - Extracted legal topics
- **article_topics** - Many-to-many links

### Logs

Logs are saved to `logs/`:
- `fetch.log` - Article collection logs
- `compile.log` - Topic extraction logs
- `generate.log` - Article generation logs

## Data Sources

Current sources (5-10 for MVP):

**RSS Feeds:**
- Slaw (legal magazine)
- Michael Geist (technology law)
- McCarthy Tétrault (employment law)
- Monkhouse Law (employment)
- Rudner Law (employment)

**APIs:**
- CanLII (Canadian case law)

**Web Scraping:**
- Ontario Court of Appeal
- Supreme Court of Canada

## Database Schema

```sql
articles (
    id, url [UNIQUE], title, content, summary,
    source, published_date, fetched_date, processed
)

topics (
    id, topic_name [UNIQUE], category, key_entity,
    smb_relevance_score [0-10], created_date
)

article_topics (
    article_id, topic_id [PRIMARY KEY]
)
```

## Typical Workflow

### Initial Setup and First Run
```bash
# Collect articles from all sources
python fetch.py          # Fetches 20-100 articles

# Extract topics with SMB relevance scores
python compile.py        # Extracts 10-30 topics with scores

# Browse and select topics to generate
python view_topics.py --min-relevance 7

# Output example:
# ID    SMB  Articles  Date Range           Topic Name
# ================================================================
# 12    🟢 9   4        2025-01-10 → ...    Smith v. Jones - Wrongful Dismissal
# 8     🟢 8   3        2025-01-09 → ...    Bill C-27 - Privacy Law Updates
# 15    🟡 7   2        2025-01-08 → ...    CRA Remote Work Guidelines

# Generate specific topics
python generate.py --topics 12,8,15

# Or generate all high-relevance topics
python generate.py --min-relevance 8
```

### Daily Updates
```bash
# Fetch new articles
python fetch.py          # Duplicates automatically skipped

# Extract topics from new articles
python compile.py        # Only processes unprocessed articles

# Browse recent topics
python view_topics.py --recent-days 7 --min-relevance 7

# Generate selected topics
python generate.py --topics <selected_ids>
```

### Filtering and Selection Examples
```bash
# View only employment law topics
python view_topics.py --category "employment law"

# View topics with most sources
python view_topics.py --min-articles 3 --sort articles

# View details for specific topic
python view_topics.py --id 5

# Generate all eligible topics (careful - may be many)
python generate.py --all
```

## Costs

**API Usage (estimated monthly):**
- OpenAI GPT-4: ~$30/month (topic extraction)
- Anthropic Claude: ~$15/month (article writing)
- **Total: ~$45/month**

## Troubleshooting

**No articles fetched:**
- Check internet connection
- Verify source URLs are accessible
- Check logs: `tail logs/fetch.log`

**Topic extraction fails:**
- Verify OPENAI_API_KEY is set correctly
- Check API quota/billing
- Review logs: `tail logs/compile.log`

**Article generation fails:**
- Verify ANTHROPIC_API_KEY is set correctly
- Ensure topics have multiple articles (need 2+ sources)
- Review logs: `tail logs/generate.log`

**Database errors:**
- Delete `data/pipeline.db` and re-initialize
- Check file permissions

## Future Enhancements

- [ ] Add more sources (expand from 10 to 50+)
- [ ] Implement automated scheduling (cron/scheduler)
- [ ] Add web dashboard for browsing topics (currently CLI-based)
- [ ] Implement email newsletter automation
- [ ] Per-site content extractors (better quality)
- [ ] Topic merging and deduplication UI
- [ ] Export topics to CSV/JSON for external analysis
- [ ] Historical tracking of topic popularity over time

## Project Structure

```
Automated_news_pipeline/
├── main.py              # Main orchestration
├── database.py          # SQLite operations
├── config.py            # Source configurations
├── fetch.py             # Phase 1: Data collection
├── compile.py           # Phase 2: Topic extraction (with SMB scoring)
├── view_topics.py       # Phase 3: Topic browser and selection
├── generate.py          # Phase 4: Article synthesis
├── requirements.txt
├── .env                 # API keys (gitignored)
├── README.md
├── data/
│   └── pipeline.db      # SQLite database (includes SMB scores)
├── output/
│   └── articles/        # Generated markdown files
└── logs/
    ├── fetch.log
    ├── compile.log
    └── generate.log
```

## License

[Your license here]
```

### Success Criteria:

#### Automated Verification:
- [ ] Main script runs: `python main.py --help`
- [ ] Full pipeline executes: `python main.py full` (runs all phases)
- [ ] Individual phases work: `python main.py fetch && python main.py compile && python main.py generate`
- [ ] README exists and has all sections: `grep -c "## " README.md`

#### Manual Verification:
- [ ] Read through README and verify all instructions are clear
- [ ] Follow setup instructions from scratch in new terminal
- [ ] Verify API key setup instructions work
- [ ] Test all CLI commands listed in README
- [ ] Confirm troubleshooting section covers common issues
- [ ] Verify example outputs match actual outputs

**Implementation Note**: The pipeline is now complete. Test the full workflow end-to-end before considering it production-ready.

---

## Testing Strategy

### Unit Testing

**Not included in MVP** - Focus on manual testing initially. Future enhancement.

### Integration Testing

**Manual end-to-end test:**
```bash
# 1. Fresh start
rm -f data/pipeline.db logs/*.log
rm -f output/articles/*

# 2. Run full pipeline
python main.py full

# 3. Verify results
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM articles;"  # Should be > 20
sqlite3 data/pipeline.db "SELECT COUNT(*) FROM topics;"    # Should be > 5
ls output/articles/*.md | wc -l                            # Should be > 3

# 4. Check logs for errors
grep ERROR logs/*.log

# 5. Read a generated article
cat output/articles/001_*.md
```

### Manual Testing Steps

After implementation:

1. **Phase 1 Testing:**
   - Run `python fetch.py`
   - Check database: `sqlite3 data/pipeline.db "SELECT source, COUNT(*) FROM articles GROUP BY source;"`
   - Verify multiple sources fetched
   - Run again, confirm duplicates skipped

2. **Phase 2 Testing:**
   - Run `python compile.py`
   - Check topics: `sqlite3 data/pipeline.db "SELECT topic_name, COUNT(*) as articles FROM topics t JOIN article_topics at ON t.id = at.topic_id GROUP BY t.id ORDER BY articles DESC;"`
   - Verify topic names are normalized
   - Check that multi-topic articles exist

3. **Phase 3 Testing:**
   - Run `python generate.py`
   - Read 3-5 generated articles
   - Verify synthesis quality (not just copying one source)
   - Check metadata in frontmatter
   - Confirm sources are cited

## Performance Considerations

**Current Design:**
- Sequential processing (one article/topic at a time)
- LLM calls are synchronous
- No rate limiting implemented

**Expected Performance:**
- Phase 1 (fetch): 5-10 minutes for ~50 articles
- Phase 2 (compile): 10-20 minutes for ~50 articles (GPT-4 calls)
- Phase 3 (generate): 5-15 minutes for ~10 articles (Claude calls)
- **Total: ~30 minutes for full pipeline**

**Future Optimizations:**
- Batch LLM calls where possible
- Parallel processing for independent tasks
- Caching of LLM responses
- Rate limiting for API calls

## Migration Notes

**Not applicable** - This is a greenfield implementation with no existing system to migrate from.

## References

- Original discussion: This chat conversation
- OpenAI API: https://platform.openai.com/docs
- Anthropic API: https://docs.anthropic.com/
- CanLII API: https://www.canlii.org/en/info/api.html
- BeautifulSoup: https://www.crummy.com/software/BeautifulSoup/
- Feedparser: https://feedparser.readthedocs.io/
