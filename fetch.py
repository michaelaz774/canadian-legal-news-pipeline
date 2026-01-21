"""
Data Collection Module for Canadian Legal News Pipeline
Fetches articles from RSS feeds, APIs, and web scraping

PHASE 1 OF PIPELINE: INFO RETRIEVAL
This module collects raw articles from multiple sources and saves them to the database.

KEY DESIGN PRINCIPLES:
1. Fail gracefully: If one source fails, continue with others
2. Log everything: Track what worked and what didn't
3. Avoid duplicates: Database handles this with UNIQUE constraint on URL
4. Be respectful: Add delays, use timeouts, identify our bot

FLOW:
fetch.py → database.py → SQLite
  ↓
For each source in config.SOURCES:
  1. Determine type (RSS/API/scrape)
  2. Call appropriate fetcher function
  3. Extract article data (title, URL, content, etc.)
  4. Fetch full content if needed
  5. Save batch to database
  6. Log results
"""

import feedparser  # Parse RSS/Atom feeds
import requests    # Make HTTP requests
from bs4 import BeautifulSoup  # Parse HTML
from database import Database
from config import SOURCES, REQUEST_TIMEOUT, USER_AGENT
import logging
from datetime import datetime
from typing import Dict, List
import os
import time

# ============================================================================
# LOGGING SETUP
# ============================================================================
# WHY LOGGING IS CRITICAL:
# - Debugging: "Why did source X fail?"
# - Monitoring: "How many articles did we fetch today?"
# - Performance: "Which sources are slow?"
# - History: "When did source X start failing?"
#
# LOG LEVELS:
# - DEBUG: Detailed info for debugging (e.g., "Parsing feed entry 5...")
# - INFO: General progress (e.g., "Fetching from Slaw...")
# - WARNING: Something unexpected but not fatal (e.g., "Could not fetch content from URL")
# - ERROR: Something failed (e.g., "RSS feed returned 404")
# ============================================================================

logging.basicConfig(
    filename='logs/fetch.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# LOGGING FORMAT EXPLAINED:
# %(asctime)s - Timestamp: "2026-01-13 14:30:15,123"
# %(levelname)s - Level: "INFO", "ERROR", etc.
# %(message)s - Your log message: "Fetching from Slaw..."
#
# EXAMPLE LOG OUTPUT:
# 2026-01-13 14:30:15,123 - INFO - Starting fetch process
# 2026-01-13 14:30:16,456 - INFO - Fetching from Slaw...
# 2026-01-13 14:30:18,789 - ERROR - Error fetching RSS from Source X: Connection timeout

# ============================================================================
# RSS FEED FETCHING
# ============================================================================

def fetch_rss(source: Dict) -> List[Dict]:
    """
    Fetch articles from an RSS feed.

    RSS (Really Simple Syndication) is an XML format designed for content distribution.
    It's the easiest source type because it's standardized and structured.

    HOW RSS WORKS:
    1. Website publishes XML file at /feed/ or /rss/
    2. XML contains list of recent articles
    3. Each article (called an "entry") has: title, link, summary, date
    4. feedparser library parses XML into Python objects

    EXAMPLE RSS XML:
    <rss>
      <channel>
        <item>
          <title>New Employment Law Case</title>
          <link>https://site.com/article</link>
          <description>Summary of the case...</description>
          <pubDate>Mon, 13 Jan 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>

    Args:
        source: Dictionary from config.SOURCES with 'name', 'url', etc.

    Returns:
        List of article dictionaries, empty list if error

    ARTICLE DICTIONARY FORMAT:
    {
        'url': 'https://...',
        'title': 'Article Title',
        'content': 'Full article text...',
        'summary': 'Brief summary',
        'source': 'Slaw',
        'published_date': '2026-01-13T10:00:00',
        'fetched_date': '2026-01-13T14:30:00'
    }
    """
    try:
        logging.info(f"Fetching RSS feed from {source['name']}: {source['url']}")

        # Parse the RSS feed
        # feedparser.parse() handles all the XML parsing complexity
        # It works with RSS 1.0, RSS 2.0, Atom feeds automatically
        feed = feedparser.parse(source['url'])

        # CHECK FOR ERRORS
        # feedparser doesn't raise exceptions; it sets status codes
        if hasattr(feed, 'status') and feed.status >= 400:
            logging.error(f"RSS feed returned HTTP {feed.status}: {source['url']}")
            return []

        if hasattr(feed, 'bozo') and feed.bozo:
            # "bozo" means the feed is malformed but feedparser tried to parse anyway
            logging.warning(f"RSS feed is malformed but parseable: {source['name']}")

        articles = []

        # ITERATE THROUGH ENTRIES
        # feed.entries is a list of articles in the feed
        # Each entry is an object with attributes like .title, .link, .summary
        for entry in feed.entries:
            # EXTRACT CONTENT
            # Different feeds provide content in different ways:
            # - Some have entry.content (full text)
            # - Some only have entry.summary (brief excerpt)
            # - Some have both
            # We prefer full content if available
            content = ''
            if hasattr(entry, 'content'):
                # entry.content is usually a list with one item
                content = entry.content[0].value
            elif hasattr(entry, 'summary'):
                content = entry.summary

            # EXTRACT DATE
            # Different feeds use different date fields:
            # - entry.published (most common)
            # - entry.updated (some feeds)
            # - entry.created (rare)
            published_date = ''
            if hasattr(entry, 'published'):
                published_date = entry.published
            elif hasattr(entry, 'updated'):
                published_date = entry.updated

            # BUILD ARTICLE DICTIONARY
            articles.append({
                'url': entry.link,
                'title': entry.title,
                'content': content,
                'summary': entry.get('summary', ''),  # .get() returns '' if key missing
                'source': source['name'],
                'published_date': published_date,
                'fetched_date': datetime.now().isoformat()
            })

        logging.info(f"Successfully fetched {len(articles)} articles from {source['name']}")
        return articles

    except Exception as e:
        # Catch ANY error (network issues, parsing errors, etc.)
        # Log it and return empty list (don't crash the whole pipeline)
        logging.error(f"Error fetching RSS from {source['name']}: {e}")
        return []

# ============================================================================
# API FETCHING (CanLII)
# ============================================================================

def fetch_canlii_api(source: Dict) -> List[Dict]:
    """
    Fetch articles from the CanLII API.

    CanLII (Canadian Legal Information Institute) provides a free API for
    accessing Canadian case law. This is more reliable than scraping because:
    - Structured JSON responses
    - Designed for programmatic access
    - Includes metadata (court, date, keywords)

    API DOCUMENTATION:
    https://www.canlii.org/en/info/api.html

    HOW IT WORKS:
    1. Register for free API key at CanLII website (https://www.canlii.org/en/feedback/feedback.html)
    2. Configure specific database IDs in config.py (e.g., 'csc-scc', 'onca')
    3. Make GET request: /v1/caseBrowse/en/{databaseId}/?offset=0&resultCount=50&api_key={key}
    4. Parse JSON response and extract case metadata
    5. Construct CanLII URLs from database ID and case ID

    CORRECT API RESPONSE FORMAT:
    {
      "cases": [
        {
          "databaseId": "onca",
          "caseId": {"en": "2014onca925"},
          "title": "Ariston Realty Corp. v. Elcarim Inc.",
          "citation": "2014 ONCA 925 (CanLII)"
        },
        ...
      ]
    }

    NOTE: The browse endpoint returns basic metadata only.
    Full case text would require additional API calls to metadata endpoint.

    Args:
        source: Dictionary from config.SOURCES

    Returns:
        List of article dictionaries
    """
    try:
        logging.info(f"Fetching from CanLII API: {source['url']}")

        # GET API KEY FROM ENVIRONMENT
        # We don't hardcode API keys in source code (security risk!)
        # Instead, read from environment variable set in .env file
        api_key = os.getenv(source['api_key_env'])

        if not api_key:
            logging.warning(f"No API key found for {source['name']} (${source['api_key_env']} not set)")
            return []

        # BUILD API REQUEST PARAMETERS
        # Most APIs accept parameters as query string: ?api_key=xxx&offset=0&resultCount=50
        params = {
            'api_key': api_key,
            'offset': 0,              # Start from result 0 (pagination)
            'resultCount': 50         # Get up to 50 results
        }

        # MAKE HTTP GET REQUEST
        # requests.get() makes an HTTP request and returns response object
        # timeout=REQUEST_TIMEOUT prevents hanging forever if server is slow
        response = requests.get(
            source['url'],
            params=params,
            timeout=REQUEST_TIMEOUT,
            headers={'User-Agent': USER_AGENT}  # Identify our bot
        )

        # CHECK FOR HTTP ERRORS
        # response.raise_for_status() raises exception if status code is 4xx or 5xx
        # 200 = OK, 404 = Not Found, 500 = Server Error, etc.
        response.raise_for_status()

        # PARSE JSON RESPONSE
        # response.json() parses JSON string into Python dictionary
        data = response.json()

        articles = []

        # ITERATE THROUGH RESULTS
        # Based on CanLII API documentation, response structure is:
        # {
        #   "cases": [
        #     {
        #       "databaseId": "onca",
        #       "caseId": {"en": "2014onca925"},
        #       "title": "Ariston Realty Corp. v. Elcarim Inc.",
        #       "citation": "2014 ONCA 925 (CanLII)"
        #     },
        #     ...
        #   ]
        # }
        #
        # NOTE: API does NOT return URL directly - we construct it from caseId
        # CanLII URL format: https://canlii.ca/t/{shortId}
        # But for simplicity, we'll use the full citation as a placeholder
        for case in data.get('cases', []):
            # Extract caseId from nested structure
            case_id_obj = case.get('caseId', {})
            case_id = case_id_obj.get('en', '') if isinstance(case_id_obj, dict) else str(case_id_obj)

            # Construct URL (CanLII uses short URLs like canlii.ca/t/abc123)
            # Without metadata endpoint, we'll use the database and caseId
            database_id = case.get('databaseId', source.get('database_id', ''))
            url = f"https://www.canlii.org/en/{database_id}/doc/{case_id}/index.html" if case_id else ''

            articles.append({
                'url': url,
                'title': case.get('title', ''),
                'content': '',  # CanLII browse API doesn't return full case text
                'summary': case.get('citation', ''),  # Use citation as summary
                'source': source['name'],
                'published_date': '',  # Date not included in browse response
                'fetched_date': datetime.now().isoformat()
            })

        logging.info(f"Successfully fetched {len(articles)} cases from {source['name']}")
        return articles

    except requests.exceptions.Timeout:
        logging.error(f"Timeout fetching from {source['name']}")
        return []

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error fetching from {source['name']}: {e}")
        return []

    except Exception as e:
        logging.error(f"Error fetching API from {source['name']}: {e}")
        return []

# ============================================================================
# WEB SCRAPING
# ============================================================================

def scrape_website(source: Dict) -> List[Dict]:
    """
    Scrape articles from a website using BeautifulSoup.

    WEB SCRAPING IS THE LAST RESORT because:
    - Fragile: Breaks when website design changes
    - Requires manual inspection to find CSS selectors
    - May encounter anti-scraping measures (CAPTCHAs, rate limits)
    - Legal considerations: Check robots.txt and terms of service

    HOW WEB SCRAPING WORKS:
    1. Make HTTP GET request to URL
    2. Receive HTML response
    3. Parse HTML into a tree structure (DOM)
    4. Use CSS selectors to find specific elements
    5. Extract text content from those elements

    CSS SELECTORS CRASH COURSE:
    - .class-name : Elements with class="class-name"
    - #id-name : Element with id="id-name"
    - tag : All elements of that tag (div, h3, a, etc.)
    - .parent .child : .child elements inside .parent elements
    - .class tag : tag elements inside .class elements

    EXAMPLE HTML:
    <div class="decision-row">
      <h3>Smith v. Jones, 2026 ONCA 123</h3>
      <a href="/case/123">Read Full Decision</a>
      <span class="date">2026-01-10</span>
    </div>

    SELECTORS FOR THIS HTML:
    - container: '.decision-row'
    - title: 'h3'
    - link: 'a'
    - date: '.date'

    Args:
        source: Dictionary from config.SOURCES with 'selectors' key

    Returns:
        List of article dictionaries
    """
    try:
        logging.info(f"Scraping website {source['name']}: {source['url']}")

        # MAKE HTTP REQUEST
        response = requests.get(
            source['url'],
            timeout=REQUEST_TIMEOUT,
            headers={'User-Agent': USER_AGENT}  # Some sites block requests without User-Agent
        )
        response.raise_for_status()

        # PARSE HTML WITH BEAUTIFULSOUP
        # BeautifulSoup converts HTML string into a tree structure
        # 'html.parser' is the built-in Python parser (no extra dependencies)
        # Alternative parsers: 'lxml' (faster but requires lxml library)
        soup = BeautifulSoup(response.content, 'html.parser')

        articles = []
        selectors = source['selectors']

        # FIND ALL CONTAINER ELEMENTS
        # soup.select() uses CSS selectors to find elements
        # Returns a list of all matching elements
        # Example: soup.select('.decision-row') finds all <div class="decision-row">
        containers = soup.select(selectors['container'])

        if not containers:
            logging.warning(f"No containers found with selector '{selectors['container']}' on {source['name']}")
            return []

        logging.debug(f"Found {len(containers)} containers on {source['name']}")

        # ITERATE THROUGH EACH CONTAINER
        for item in containers:
            try:
                # FIND ELEMENTS WITHIN THIS CONTAINER
                # item.select_one() finds the FIRST matching element within item
                # Returns None if not found
                title_elem = item.select_one(selectors['title'])
                link_elem = item.select_one(selectors['link'])
                date_elem = item.select_one(selectors.get('date', ''))

                # CHECK REQUIRED ELEMENTS EXIST
                if not title_elem or not link_elem:
                    logging.debug(f"Skipping item: missing title or link")
                    continue

                # EXTRACT URL
                url = link_elem.get('href', '')  # Get href attribute from <a> tag

                # MAKE URL ABSOLUTE IF IT'S RELATIVE
                # Some sites use relative URLs: href="/case/123"
                # We need absolute URLs: "https://site.com/case/123"
                if url.startswith('/'):
                    from urllib.parse import urljoin
                    # urljoin() combines base URL with relative URL
                    # Example: urljoin('https://site.com/page', '/case/123') → 'https://site.com/case/123'
                    url = urljoin(source['url'], url)

                # EXTRACT TEXT CONTENT
                # elem.text.strip() gets the text content and removes leading/trailing whitespace
                # Example: <h3>  Smith v. Jones  </h3> → "Smith v. Jones"
                title = title_elem.text.strip()
                published_date = date_elem.text.strip() if date_elem else ''

                articles.append({
                    'url': url,
                    'title': title,
                    'content': '',  # Will be fetched separately by fetch_full_content()
                    'summary': '',
                    'source': source['name'],
                    'published_date': published_date,
                    'fetched_date': datetime.now().isoformat()
                })

            except Exception as e:
                # If one item fails, log it and continue with others
                logging.warning(f"Error parsing item in {source['name']}: {e}")
                continue

        logging.info(f"Successfully scraped {len(articles)} articles from {source['name']}")
        return articles

    except requests.exceptions.Timeout:
        logging.error(f"Timeout scraping {source['name']}")
        return []

    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error scraping {source['name']}: {e}")
        return []

    except Exception as e:
        logging.error(f"Error scraping {source['name']}: {e}")
        return []

# ============================================================================
# FULL CONTENT FETCHING
# ============================================================================

def fetch_full_content(url: str) -> str:
    """
    Fetch full article content from a URL.

    WHEN THIS IS USED:
    - RSS feeds often only include summaries, not full text
    - Scraped articles initially have empty content
    - We need full text for topic extraction in compile.py

    HOW IT WORKS:
    1. Make HTTP request to article URL
    2. Parse HTML
    3. Remove unwanted elements (nav, footer, ads, scripts)
    4. Try to find main content area
    5. Extract all text

    THIS IS A "BEST EFFORT" APPROACH:
    - No single method works for all websites
    - We try common patterns (<article>, <main>, etc.)
    - Some sites may require custom extractors (future enhancement)

    Args:
        url: Full URL to the article

    Returns:
        String with full article text, empty string if failed
    """
    try:
        logging.debug(f"Fetching full content from {url}")

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={'User-Agent': USER_AGENT}
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # REMOVE UNWANTED ELEMENTS
        # These elements don't contain article content, so remove them
        # decompose() completely removes the element from the tree
        unwanted_tags = ['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']
        for tag in unwanted_tags:
            for element in soup.find_all(tag):
                element.decompose()

        # TRY TO FIND MAIN CONTENT AREA
        # Most websites use semantic HTML tags or common class names
        # We try these in order of specificity:
        # 1. <article> tag (semantic HTML5 for article content)
        # 2. <main> tag (semantic HTML5 for main content)
        # 3. <body> tag (fallback: entire page body)
        article = soup.find('article') or soup.find('main') or soup.find('body')

        if article:
            # EXTRACT TEXT CONTENT
            # get_text() extracts all text from element and its children
            # separator='\n' puts newlines between text from different elements
            # strip=True removes leading/trailing whitespace
            # Example:
            # <article>
            #   <h1>Title</h1>
            #   <p>Paragraph 1</p>
            #   <p>Paragraph 2</p>
            # </article>
            # →
            # "Title\nParagraph 1\nParagraph 2"
            text = article.get_text(separator='\n', strip=True)

            # LIMIT LENGTH TO AVOID TOKEN LIMITS
            # Very long articles may exceed LLM token limits
            # We take first 10000 characters (roughly 2500 words)
            # compile.py further limits to 3000 characters for GPT-4
            return text[:10000]

        return ""

    except Exception as e:
        # Don't crash if content fetching fails
        # Article will be saved with empty content
        # compile.py can still work with title and summary
        logging.warning(f"Could not fetch content from {url}: {e}")
        return ""

# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

def main():
    """
    Main fetch process - orchestrates fetching from all sources.

    WORKFLOW:
    1. Initialize database connection
    2. For each source in config:
       a. Determine source type (RSS/API/scrape)
       b. Call appropriate fetcher function
       c. Fetch full content for articles that need it
       d. Save batch to database (duplicates auto-skipped)
    3. Print summary statistics

    ERROR HANDLING STRATEGY:
    - If one source fails, log it and continue with others
    - Better to get partial data than no data
    - User can check logs to see what failed

    DUPLICATE HANDLING:
    - Database has UNIQUE constraint on url column
    - insert_articles_batch() catches IntegrityError for duplicates
    - Returns (inserted, skipped) counts
    - This makes fetch.py IDEMPOTENT: safe to run multiple times

    PERFORMANCE:
    - Sequential processing (one source at a time)
    - Could be parallelized in future (threading/asyncio)
    - Full content fetching is the slowest part
    """
    logging.info("=" * 50)
    logging.info("Starting fetch process")
    print("\n" + "=" * 60)
    print("FETCHING ARTICLES FROM CANADIAN LEGAL SOURCES")
    print("=" * 60)

    # INITIALIZE DATABASE
    db = Database()

    # COLLECT ALL ARTICLES FROM ALL SOURCES
    all_articles = []

    # ITERATE THROUGH EACH SOURCE
    for source in SOURCES:
        logging.info(f"Fetching from {source['name']}...")
        print(f"\n[{source['name']}]")
        print(f"  Type: {source['type'].upper()}")
        print(f"  URL: {source['url']}")

        try:
            # DISPATCH TO APPROPRIATE FETCHER BASED ON TYPE
            if source['type'] == 'rss':
                articles = fetch_rss(source)
            elif source['type'] == 'api':
                articles = fetch_canlii_api(source)
            elif source['type'] == 'scrape':
                articles = scrape_website(source)
            else:
                logging.warning(f"Unknown source type '{source['type']}' for {source['name']}")
                print(f"  ERROR: Unknown source type '{source['type']}'")
                continue

            # FETCH FULL CONTENT FOR ARTICLES WITHOUT IT
            # This is the slowest part (one HTTP request per article)
            # We show progress so user knows it's not frozen
            for i, article in enumerate(articles):
                if not article['content'] and article['url']:
                    # Only fetch if:
                    # 1. Content is empty (RSS summary only, or scraped without content)
                    # 2. URL exists (can't fetch without URL)
                    print(f"  Fetching full content... ({i+1}/{len(articles)})", end='\r')
                    article['content'] = fetch_full_content(article['url'])
                    # BE RESPECTFUL: Add small delay between requests
                    # Don't overwhelm the server with rapid requests
                    time.sleep(0.5)  # 500ms delay

            # CLEAR THE PROGRESS LINE
            print(" " * 60, end='\r')

            # ADD TO MASTER LIST
            all_articles.extend(articles)

            logging.info(f"  Found {len(articles)} articles from {source['name']}")
            print(f"  ✓ Found {len(articles)} articles")

        except Exception as e:
            # Catch ANY error from this source and continue
            logging.error(f"Fatal error with {source['name']}: {e}")
            print(f"  ✗ ERROR: {e}")
            continue

    # SAVE ALL ARTICLES TO DATABASE
    print(f"\n{'-' * 60}")
    print(f"SAVING TO DATABASE...")
    print(f"{'-' * 60}")
    logging.info(f"Saving {len(all_articles)} articles to database...")

    # insert_articles_batch() handles duplicates automatically
    # Returns (inserted, skipped) where skipped = duplicates
    inserted, skipped = db.insert_articles_batch(all_articles)

    logging.info(f"Inserted: {inserted}, Skipped (duplicates): {skipped}")
    print(f"  Inserted: {inserted}")
    print(f"  Skipped (duplicates): {skipped}")

    # GET FINAL STATISTICS
    stats = db.get_stats()
    logging.info(f"Database now has {stats['total_articles']} total articles")

    # PRINT SUMMARY
    print(f"\n{'=' * 60}")
    print(f"FETCH COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total articles collected: {len(all_articles)}")
    print(f"  New articles inserted: {inserted}")
    print(f"  Duplicates skipped: {skipped}")
    print(f"  Total articles in database: {stats['total_articles']}")
    print(f"  Unprocessed articles: {stats['unprocessed_articles']}")
    print(f"\nNext steps:")
    print(f"  1. Check logs/fetch.log for any errors")
    print(f"  2. Run: python compile.py")
    print(f"{'=' * 60}\n")

    logging.info("Fetch process complete")


if __name__ == '__main__':
    # This block runs when you execute: python fetch.py
    # It won't run if you import fetch as a module
    main()
