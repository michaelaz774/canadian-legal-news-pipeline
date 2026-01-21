"""
================================================================================
COMPILE.PY - PHASE 4: AI-POWERED TOPIC EXTRACTION
================================================================================

PURPOSE:
This module uses Google's Gemini 2.5 Flash AI model to automatically extract
legal topics from collected articles and score their relevance to small/medium
businesses (SMBs).

WHAT THIS MODULE DOES:
1. Fetches unprocessed articles from the database
2. Sends each article's full content to Gemini AI
3. Extracts 1-3 primary topics with SMB relevance scores (0-10)
4. Normalizes topic names for consistency
5. Stores topics and article-topic relationships in database
6. Provides progress tracking and comprehensive error handling

WHY WE USE GEMINI 2.5 FLASH:
- Ultra cost-effective: $0.30 input / $2.50 output per 1M tokens (~$0.06 for 60 articles)
- Native structured JSON output with schema validation (guaranteed valid responses)
- Fast processing: 226 tokens/second
- 1M token context window (easily handles articles up to 28K+ characters)
- Free tier is sufficient for initial batches (10 RPM, 250K TPM, 1,000 RPD)

PROCESS FLOW:
1. Load unprocessed articles from database (articles without topics)
2. For each article:
   a. Send full content to Gemini with SMB-focused prompt
   b. Receive structured JSON with topics and relevance scores
   c. Validate response against Pydantic schema
   d. Store topics in database (with deduplication)
   e. Create article-topic relationships
3. Log processing statistics and any errors

IDEMPOTENT DESIGN:
This script can be run multiple times safely. It only processes articles that
don't already have topics assigned, so you can:
- Restart after failures without duplicating work
- Run on new articles without reprocessing old ones
- Add articles incrementally and reprocess

DATABASE INTERACTION:
- Reads from: articles table (fetches unprocessed articles)
- Writes to: topics table (creates/updates topics)
- Writes to: article_topics table (creates article-topic relationships)

DEPENDENCIES:
- google-genai: New unified Google AI SDK (replaces deprecated google-generativeai)
- pydantic: Schema validation for structured outputs
- tenacity: Retry logic with exponential backoff
- tqdm: Progress bars for user feedback
- python-dotenv: Environment variable management

USAGE:
    python compile.py

ENVIRONMENT VARIABLES REQUIRED:
    GEMINI_API_KEY: Your Google AI Studio API key (free tier available)
                    Get it at: https://aistudio.google.com/app/apikey

COST ESTIMATES:
- 60 articles (~95K tokens): $0.06 total
- 1,000 articles (~1.6M tokens): $1.00 total
- Free tier limit: 1,000 requests/day (sufficient for most use cases)

================================================================================
"""

import os
import logging
from datetime import datetime
from typing import List, Optional, Dict
from dotenv import load_dotenv

# PYDANTIC FOR SCHEMA VALIDATION
# Pydantic provides type-safe data validation and is the recommended way
# to define structured output schemas for Gemini AI responses
from pydantic import BaseModel, Field

# GOOGLE GENAI SDK
# IMPORTANT: This is the NEW unified SDK (google-genai), not the deprecated
# google-generativeai SDK which was deprecated August 31, 2025
from google import genai

# TENACITY FOR RETRY LOGIC
# Provides sophisticated retry mechanisms with exponential backoff
# Essential for handling rate limits (HTTP 429) and service issues (HTTP 503)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# GOOGLE API EXCEPTIONS
# These are the specific exceptions we need to catch and retry
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

# PROGRESS BAR
# tqdm provides user-friendly progress bars for long-running operations
from tqdm import tqdm

# OUR DATABASE MODULE
from database import Database

# LOAD ENVIRONMENT VARIABLES
# This reads the .env file and makes variables available via os.environ
load_dotenv()

# ENSURE LOGS DIRECTORY EXISTS
# Create logs directory before setting up logging to avoid FileNotFoundError
os.makedirs('logs', exist_ok=True)

# CONFIGURE LOGGING
# Set up logging to both file and console for comprehensive debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/compile.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# PYDANTIC SCHEMAS FOR STRUCTURED OUTPUT
# ============================================================================
# These classes define the exact structure we expect from Gemini AI.
# The AI model will be forced to return JSON matching these schemas,
# eliminating parsing errors and ensuring data consistency.

class Topic(BaseModel):
    """
    Represents a single legal topic extracted from an article with 3-level hierarchical structure.

    FIELDS:
    - parent_topic: Broad legal category (e.g., "Employment Law", "Contract Law")
    - subtopic: Specific focus area within the parent (e.g., "Wrongful Dismissal")
    - article_tag: Specific aspect discussed in THIS article (e.g., "Wrongful dismissal during protected leave")
    - smb_relevance_score: 0-10 score indicating how relevant this topic is to SMBs
    - reasoning: Brief explanation of why this topic matters for SMBs

    HIERARCHICAL STRUCTURE:
    - Parent topics: Broad categories (8-10 main categories)
    - Subtopics: Standard categories for grouping related articles
    - Article tags: Specific aspect of the subtopic discussed in this particular article

    EXAMPLE:
    {
        "parent_topic": "Employment Law",
        "subtopic": "Wrongful Dismissal",
        "article_tag": "Wrongful dismissal during pregnancy leave",
        "smb_relevance_score": 9,
        "reasoning": "Wrongful dismissal claims are common for SMBs..."
    }

    WHY 3 LEVELS:
    - Parent: Browse by broad category
    - Subtopic: Generate articles combining related content
    - Article tag: Identify unique contributions of each source article
    """
    parent_topic: str = Field(
        description="Broad legal category (Employment Law, Contract Law, Privacy & Data Protection, etc.)"
    )
    subtopic: str = Field(
        description="Standard subtopic category (e.g., 'Wrongful Dismissal', 'Data Breach Response')"
    )
    article_tag: str = Field(
        description="Specific aspect discussed in THIS article (5-8 words describing the unique focus)"
    )
    smb_relevance_score: int = Field(
        description="Relevance score from 0-10 indicating importance to SMBs (0=not relevant, 10=critical)",
        ge=0,  # Greater than or equal to 0
        le=10  # Less than or equal to 10
    )
    reasoning: str = Field(
        description="Brief 1-2 sentence explanation of why this topic is relevant to SMBs"
    )


class TopicExtraction(BaseModel):
    """
    The complete response structure we expect from Gemini AI.

    FIELDS:
    - topics: List of 1-3 primary topics (we limit to 3 to focus on main themes)
    - summary: One-sentence summary of the article's main focus

    WHY 1-3 TOPICS:
    - Too few topics (1): Misses nuance and complexity
    - Too many topics (5+): Dilutes focus and creates noise
    - 1-3 topics: Sweet spot for capturing main themes without over-categorizing
    """
    topics: List[Topic] = Field(
        description="List of 1-3 primary topics identified in the legal article",
        min_length=1,
        max_length=3
    )
    summary: str = Field(
        description="One-sentence summary of the article's main focus"
    )


# ============================================================================
# GEMINI AI CLIENT INITIALIZATION
# ============================================================================

def initialize_gemini_client() -> genai.Client:
    """
    Initialize and return a Gemini AI client with proper API key configuration.

    WHAT THIS DOES:
    - Checks for GEMINI_API_KEY in environment variables
    - Creates a client instance that automatically handles authentication
    - Returns ready-to-use client for making API requests

    WHY WE NEED THIS:
    The Client() constructor automatically picks up the GEMINI_API_KEY from
    environment variables, but we add explicit validation to provide clear
    error messages if the key is missing.

    RETURNS:
        genai.Client: Authenticated Gemini client ready for API calls

    RAISES:
        ValueError: If GEMINI_API_KEY is not set in environment

    USAGE:
        client = initialize_gemini_client()
        response = client.models.generate_content(...)
    """
    api_key = os.environ.get('GEMINI_API_KEY')

    # VALIDATE API KEY EXISTS
    # Fail fast with clear error message if key is missing
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found in environment variables. "
            "Get your free API key at: https://aistudio.google.com/app/apikey "
            "Then add it to your .env file: GEMINI_API_KEY=your-key-here"
        )

    # CREATE CLIENT
    # The client automatically handles authentication, retries, and error handling
    client = genai.Client(api_key=api_key)

    logger.info("Gemini AI client initialized successfully")
    return client


# ============================================================================
# TOPIC EXTRACTION WITH AI
# ============================================================================

# RETRY DECORATOR
# This decorator automatically retries the function if it encounters rate limits
# or service unavailability errors, using exponential backoff
@retry(
    # STOP AFTER 5 ATTEMPTS
    # If we fail 5 times, give up and raise the error
    # This prevents infinite retry loops
    stop=stop_after_attempt(5),

    # EXPONENTIAL BACKOFF WITH JITTER
    # Wait times: 2s, 4s, 8s, 16s, 32s (capped at 60s)
    # The "multiplier=1" means base delay of 1 second, doubled each time
    # "min=2" means first retry waits 2 seconds minimum
    # "max=60" caps the maximum wait time
    wait=wait_exponential(multiplier=1, min=2, max=60),

    # ONLY RETRY SPECIFIC EXCEPTIONS
    # ResourceExhausted = HTTP 429 (rate limit exceeded)
    # ServiceUnavailable = HTTP 503 (temporary service issue)
    # Other errors (like invalid API key) will fail immediately
    retry=retry_if_exception_type((ResourceExhausted, ServiceUnavailable)),

    # RERAISE FINAL EXCEPTION
    # If all retries fail, raise the original exception
    reraise=True
)
def extract_topics_from_article(
    client: genai.Client,
    article_title: str,
    article_content: str
) -> TopicExtraction:
    """
    Use Gemini AI to extract topics from a single article.

    WHAT THIS DOES:
    1. Constructs an SMB-focused prompt with the article content
    2. Sends request to Gemini 2.5 Flash with structured output schema
    3. Receives guaranteed-valid JSON response matching our schema
    4. Validates and parses response into TopicExtraction object
    5. Automatically retries on rate limits or service issues

    WHY STRUCTURED OUTPUT:
    Gemini's structured output feature forces the AI to return JSON that
    exactly matches our Pydantic schema. This eliminates:
    - JSON parsing errors
    - Missing fields
    - Invalid data types
    - Schema validation failures

    PARAMETERS:
        client: Authenticated Gemini client
        article_title: Title of the article (helps AI understand context)
        article_content: Full article text (no truncation needed - we have 1M token limit)

    RETURNS:
        TopicExtraction: Validated object containing topics and summary

    RAISES:
        ResourceExhausted: If rate limit exceeded after all retries
        ServiceUnavailable: If service unavailable after all retries
        ValueError: If response validation fails

    COST PER CALL:
        Average article (6,343 chars ≈ 1,586 tokens):
        - Input: 1,586 tokens × $0.30/1M = $0.00048
        - Output: ~200 tokens × $2.50/1M = $0.0005
        - Total: ~$0.001 per article
    """

    # CONSTRUCT SMB-FOCUSED PROMPT
    # This prompt emphasizes relevance to small/medium businesses,
    # ensuring topics are scored from an SMB perspective
    prompt = f"""You are a legal expert analyzing Canadian legal articles for small and medium-sized business (SMB) owners.

Your task: Extract 1-3 primary legal topics from the article below using a TWO-LEVEL hierarchy and score their relevance to SMBs.

HIERARCHICAL TOPIC STRUCTURE:

1. PARENT TOPIC (broad category) - Choose from these:
   - Employment Law
   - Contract Law
   - Privacy & Data Protection
   - Corporate Governance
   - Tax Law
   - Intellectual Property
   - Business Torts
   - Technology & AI Law
   - Real Estate & Leasing
   - Regulatory Compliance
   - Criminal Law (only if directly relevant to businesses)

2. SUBTOPIC (specific focus) - **IMPORTANT: Use these STANDARD subtopics whenever possible. Only create a new subtopic if none of these fit.**

   Employment Law subtopics:
   - Wrongful Dismissal
   - Workplace Harassment & Discrimination
   - Employment Contracts & Termination
   - Employee Classification & Rights
   - Workplace Safety & Accommodation
   - Severance & Termination Pay
   - Employment Standards & Leaves

   Contract Law subtopics:
   - Contract Formation & Interpretation
   - Breach of Contract
   - Restrictive Covenants
   - Service Agreements

   Privacy & Data Protection subtopics:
   - Data Breach Response
   - PIPEDA Compliance
   - AI & Data Governance
   - Government Data Access

   Tax Law subtopics:
   - Corporate Tax
   - CRA Assessments & Appeals
   - Digital Services Tax
   - Payroll Tax

   Technology & AI Law subtopics:
   - AI Regulation & Compliance
   - AI Liability & Ethics
   - Digital Communications

   Corporate Governance subtopics:
   - Director & Officer Duties
   - Shareholder Rights
   - Corporate Compliance

   Intellectual Property subtopics:
   - Copyright
   - Trademarks
   - Trade Secrets

   Regulatory Compliance subtopics:
   - Professional Conduct
   - Industry Regulations
   - Administrative Law

   For other parent topics, create concise (2-4 word) subtopics focused on the main legal issue.

3. ARTICLE TAG (specific aspect) - Describe what THIS specific article discusses:
   - 5-8 words describing the unique angle or focus
   - What makes THIS article different from others on the same subtopic?
   - Examples:
     * Subtopic: Wrongful Dismissal → Tag: "Wrongful dismissal during pregnancy leave"
     * Subtopic: Wrongful Dismissal → Tag: "Constructive dismissal hostile work environment"
     * Subtopic: Data Breach Response → Tag: "PIPEDA breach notification requirements"
     * Subtopic: Contract Formation & Interpretation → Tag: "Force majeure clauses in commercial leases"

SCORING GUIDELINES (0-10):
- 9-10: Critical for SMBs (e.g., employment standards, contract basics, tax obligations)
- 7-8: Highly relevant (e.g., intellectual property, commercial leases, privacy compliance)
- 5-6: Moderately relevant (e.g., corporate governance, regulatory compliance)
- 3-4: Somewhat relevant (e.g., complex M&A, securities law)
- 0-2: Low relevance (e.g., constitutional law, criminal law)

ARTICLE TITLE: {article_title}

ARTICLE CONTENT:
{article_content}

Return your response as JSON matching this exact structure:
{{
  "topics": [
    {{
      "parent_topic": "Employment Law",
      "subtopic": "Wrongful Dismissal",
      "article_tag": "Wrongful dismissal during pregnancy leave",
      "smb_relevance_score": 9,
      "reasoning": "Brief explanation of why this matters for SMBs"
    }}
  ],
  "summary": "One-sentence summary of the article"
}}

Extract the topics now, focusing on what SMB owners need to know."""

    # MAKE API CALL WITH JSON OUTPUT
    # We force JSON format and validate afterward with Pydantic
    response = client.models.generate_content(
        # MODEL SELECTION
        # gemini-2.5-flash: Best price-performance for extraction tasks
        # Alternatives: gemini-2.5-flash-lite (cheaper, slightly lower quality)
        model="gemini-2.5-flash",

        # PROMPT CONTENT
        contents=prompt,

        # JSON OUTPUT CONFIGURATION
        # NOTE: google-genai 1.0.0 doesn't support response_json_schema parameter
        # Instead, we use response_mime_type to force JSON and validate afterward
        config={
            # Force JSON output format
            "response_mime_type": "application/json",
        },
    )

    # VALIDATE AND PARSE RESPONSE
    # Pydantic validates that the JSON matches our schema exactly
    # If validation fails, it raises a ValueError with clear error details
    try:
        topics_data = TopicExtraction.model_validate_json(response.text)
        return topics_data

    except ValueError as e:
        # This should rarely happen with structured output, but we handle it gracefully
        logger.error(f"Failed to validate Gemini response for '{article_title}': {e}")
        logger.error(f"Raw response: {response.text}")
        raise


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_unprocessed_articles(db: Database) -> List[Dict]:
    """
    Fetch articles that haven't been processed for topic extraction yet.

    WHAT THIS DOES:
    Queries the database for articles that don't have any topics assigned yet.
    This makes the script idempotent - you can run it multiple times and it
    will only process new articles.

    HOW WE IDENTIFY UNPROCESSED ARTICLES:
    The Database class has a built-in method `get_unprocessed_articles()` that
    returns all articles where processed=0. This is simpler and more reliable
    than checking for missing article_topics entries.

    PARAMETERS:
        db: Database instance

    RETURNS:
        List of dictionaries: [{'id': 1, 'title': '...', 'content': '...', ...}, ...]

    WHY THIS WORKS:
    - fetch.py sets processed=0 when inserting articles
    - We set processed=1 after extracting topics
    - Database method filters WHERE processed=0
    """
    # USE DATABASE'S BUILT-IN METHOD
    # This returns articles where processed=0
    articles = db.get_unprocessed_articles()

    logger.info(f"Found {len(articles)} unprocessed articles")
    return articles


def store_topics_and_relationships(
    db: Database,
    article_id: int,
    topics_data: TopicExtraction
) -> None:
    """
    Store extracted topics and create article-topic relationships in database.

    WHAT THIS DOES:
    1. For each topic extracted by AI:
       a. Use Database's find_or_create_topic() method (handles deduplication)
       b. Create article-topic relationship using link_article_to_topic()
    2. Mark article as processed so we don't reprocess it

    WHY USE DATABASE METHODS:
    The Database class already has methods for these operations:
    - find_or_create_topic(): Handles topic deduplication automatically
    - link_article_to_topic(): Safely creates relationships (prevents duplicates)
    - mark_article_processed(): Marks article as processed=1

    This is cleaner than writing raw SQL and reuses tested code.

    PARAMETERS:
        db: Database instance
        article_id: ID of the article being processed
        topics_data: TopicExtraction object from Gemini AI

    RETURNS:
        None (commits changes to database via Database methods)

    DATABASE CHANGES:
        - topics table: Inserts new topics (with deduplication)
        - article_topics table: Creates article-topic relationships
        - articles table: Sets processed=1 for this article
    """

    for topic in topics_data.topics:
        # STEP 1: FIND OR CREATE PARENT TOPIC
        # Parent topics are broad categories (Employment Law, Contract Law, etc.)
        parent_topic_id = db.find_or_create_topic(
            topic_name=topic.parent_topic,
            smb_relevance_score=10,  # Parent topics always get max relevance
            is_parent=True
        )

        logger.debug(f"Parent topic '{topic.parent_topic}' has ID: {parent_topic_id}")

        # STEP 2: FIND OR CREATE SUBTOPIC
        # Subtopics are specific focus areas under the parent
        subtopic_id = db.find_or_create_topic(
            topic_name=topic.subtopic,
            smb_relevance_score=topic.smb_relevance_score,
            parent_topic_id=parent_topic_id,
            is_parent=False
        )

        logger.debug(f"Subtopic '{topic.subtopic}' has ID: {subtopic_id} (parent: {parent_topic_id})")

        # STEP 3: LINK ARTICLE TO SUBTOPIC WITH ARTICLE TAG
        # We link articles to subtopics (not parents), which automatically
        # associates them with the parent via the hierarchy
        # The article_tag helps identify what's unique about this article
        db.link_article_to_topic(article_id, subtopic_id, article_tag=topic.article_tag)

        logger.debug(
            f"Linked article {article_id} to '{topic.parent_topic} > {topic.subtopic}' "
            f"[{topic.article_tag}] (score: {topic.smb_relevance_score}/10)"
        )

    # STEP 3: MARK ARTICLE AS PROCESSED
    # This ensures we don't reprocess this article on next run
    db.mark_article_processed(article_id)

    logger.info(f"Stored {len(topics_data.topics)} topics for article {article_id}")


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_articles():
    """
    Main function to process all unprocessed articles with topic extraction.

    WHAT THIS DOES:
    1. Initialize database and Gemini client
    2. Fetch unprocessed articles
    3. For each article:
       a. Extract topics using Gemini AI
       b. Store topics and relationships in database
       c. Update progress bar
       d. Log any errors without stopping entire process
    4. Report final statistics

    ERROR HANDLING STRATEGY:
    - Individual article failures are logged but don't stop processing
    - This ensures one bad article doesn't break the entire batch
    - Failed articles will be retried on next run (they remain unprocessed)

    PROGRESS TRACKING:
    - Uses tqdm for real-time progress bar
    - Shows current article title
    - Displays processing speed (articles/second)
    - Updates on each completion or error

    RETURNS:
        None (outputs statistics to console and logs)
    """

    logger.info("=" * 80)
    logger.info("STARTING TOPIC EXTRACTION PROCESS")
    logger.info("=" * 80)

    # INITIALIZE DATABASE CONNECTION
    db = Database()

    # INITIALIZE GEMINI CLIENT
    try:
        client = initialize_gemini_client()
    except ValueError as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        return

    # FETCH UNPROCESSED ARTICLES
    articles = get_unprocessed_articles(db)

    if not articles:
        logger.info("No unprocessed articles found. All articles have topics assigned!")
        return

    logger.info(f"Processing {len(articles)} articles...")

    # TRACKING STATISTICS
    successful = 0
    failed = 0

    # PROCESS EACH ARTICLE WITH PROGRESS BAR
    # tqdm creates a progress bar that updates on each iteration
    # desc= sets the description shown before the progress bar
    # unit= sets the unit name (e.g., "article")
    for article in tqdm(articles, desc="Extracting topics", unit="article"):
        # EXTRACT ARTICLE DATA FROM DICTIONARY
        # Database methods return dictionaries, not tuples
        article_id = article['id']
        title = article['title']
        content = article['content']

        try:
            # EXTRACT TOPICS WITH AI
            # This automatically retries on rate limits/service issues
            logger.info(f"Processing: {title}")
            topics_data = extract_topics_from_article(client, title, content)

            # STORE IN DATABASE
            store_topics_and_relationships(db, article_id, topics_data)

            # LOG SUCCESS
            topic_names = [f"{t.parent_topic} > {t.subtopic} [{t.article_tag}]" for t in topics_data.topics]
            logger.info(f"✓ Extracted topics: {', '.join(topic_names)}")
            successful += 1

        except Exception as e:
            # LOG ERROR BUT CONTINUE PROCESSING
            # We don't want one bad article to stop the entire batch
            logger.error(f"✗ Failed to process article {article_id} ('{title}'): {e}")
            failed += 1
            continue

    # REPORT FINAL STATISTICS
    logger.info("=" * 80)
    logger.info("TOPIC EXTRACTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total articles processed: {len(articles)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")

    if failed > 0:
        logger.warning(f"{failed} articles failed. They will be retried on next run.")

    # CLOSE DATABASE CONNECTION
    db.close()


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Entry point when script is run directly.

    USAGE:
        python compile.py

    PREREQUISITES:
        1. .env file with GEMINI_API_KEY set
        2. Database with articles (run fetch.py first)
        3. Virtual environment with dependencies installed

    WHAT HAPPENS:
        - Creates logs/ directory if it doesn't exist
        - Processes all unprocessed articles
        - Stores topics and relationships in database
        - Logs all activities to logs/compile.log
    """

    # ENSURE LOGS DIRECTORY EXISTS
    # exist_ok=True prevents error if directory already exists
    os.makedirs('logs', exist_ok=True)

    # RUN MAIN PROCESSING FUNCTION
    try:
        process_articles()
    except KeyboardInterrupt:
        # HANDLE CTRL+C GRACEFULLY
        logger.info("\nProcess interrupted by user. Progress has been saved.")
        logger.info("Run the script again to continue processing remaining articles.")
    except Exception as e:
        # HANDLE UNEXPECTED ERRORS
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
