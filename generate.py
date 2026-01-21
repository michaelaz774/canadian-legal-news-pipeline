"""
================================================================================
GENERATE.PY - PHASE 6: AI-POWERED ARTICLE SYNTHESIS
================================================================================

PURPOSE:
This module uses Anthropic's Claude AI to synthesize multiple source articles
into comprehensive, SMB-focused articles that combine insights from various
legal sources.

WHAT THIS MODULE DOES:
1. Takes a topic ID (e.g., "Employment Law")
2. Fetches all articles discussing that topic from the database
3. Sends articles to Claude with SMB-focused synthesis prompt
4. Generates a new comprehensive article combining insights
5. Saves the synthesized article to output/generated_articles/
6. Tracks generation metadata (topic, sources, date, word count)

WHY WE USE CLAUDE (NOT GEMINI):
- Superior long-form writing quality and coherence
- Excellent at synthesizing multiple sources into cohesive narratives
- Better tone control for professional legal content
- Strong at explaining complex concepts for lay audiences
- Cost-effective: Claude Sonnet 4.5 or Haiku 4.5

SYNTHESIS APPROACH:
This is NOT simple summarization. Claude will:
1. Identify common themes across articles
2. Extract key insights and practical takeaways
3. Combine complementary perspectives
4. Organize into logical flow for SMB owners
5. Add practical advice and action items
6. Maintain professional but accessible tone

WORKFLOW:
1. User runs view_topics.py → Identifies topic ID (e.g., ID: 5)
2. User runs: python generate.py --topic 5
3. Script fetches all articles for topic 5
4. Sends to Claude for synthesis
5. Saves output to output/generated_articles/employment_law_2026_01_20.md
6. Displays generation statistics

OUTPUT FORMAT:
Markdown files with metadata header:
---
topic: Employment Law
generated_date: 2026-01-20
source_count: 5
model: claude-sonnet-4-5-20250929
word_count: 1842
---

# Employment Law Essentials for Canadian SMBs

[Synthesized article content...]

USAGE:
    # Generate article for single topic
    python generate.py --topic 5

    # Generate articles for multiple topics
    python generate.py --topics 5 12 8

    # Generate from exported list
    python generate.py --topics-file topics_to_generate.txt

    # Use Claude Haiku (faster, cheaper)
    python generate.py --topic 5 --model haiku

ENVIRONMENT VARIABLES REQUIRED:
    ANTHROPIC_API_KEY: Your Anthropic API key for Claude access

COST ESTIMATES (Claude Sonnet 4.5):
- Input: 30K tokens (multiple source articles) × $3/1M = $0.09
- Output: 2K tokens (synthesized article) × $15/1M = $0.03
- Total per article: ~$0.12

COST ESTIMATES (Claude Haiku 4.5):
- Input: 30K tokens × $0.25/1M = $0.0075
- Output: 2K tokens × $1.25/1M = $0.0025
- Total per article: ~$0.01 (12× cheaper)

================================================================================
"""

import os
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

# ANTHROPIC SDK
# Official Python SDK for Claude AI models
from anthropic import Anthropic

# OUR DATABASE MODULE
from database import Database

# LOAD ENVIRONMENT VARIABLES
load_dotenv()

# ENSURE LOGS DIRECTORY EXISTS
# Create logs directory before setting up logging to avoid FileNotFoundError
os.makedirs('logs', exist_ok=True)

# CONFIGURE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/generate.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CLAUDE CLIENT INITIALIZATION
# ============================================================================

def initialize_claude_client() -> Anthropic:
    """
    Initialize and return an Anthropic client for Claude API.

    WHAT THIS DOES:
    - Checks for ANTHROPIC_API_KEY in environment variables
    - Creates authenticated client for making API requests
    - Returns ready-to-use client

    RETURNS:
        Anthropic: Authenticated client ready for API calls

    RAISES:
        ValueError: If ANTHROPIC_API_KEY is not set

    USAGE:
        client = initialize_claude_client()
        response = client.messages.create(...)
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')

    # VALIDATE API KEY EXISTS
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found in environment variables. "
            "Add it to your .env file: ANTHROPIC_API_KEY=sk-ant-your-key-here"
        )

    # CREATE CLIENT
    client = Anthropic(api_key=api_key)

    logger.info("Claude AI client initialized successfully")
    return client


# ============================================================================
# ARTICLE SYNTHESIS WITH CLAUDE
# ============================================================================

def synthesize_articles(
    client: Anthropic,
    topic_name: str,
    articles: List[Dict],
    model: str = "claude-sonnet-4-5-20250929"
) -> str:
    """
    Use Claude AI to synthesize multiple articles into one comprehensive piece.

    WHAT THIS DOES:
    1. Constructs a synthesis prompt with all source articles
    2. Sends to Claude with SMB-focused instructions
    3. Receives a comprehensive synthesized article
    4. Returns the generated content

    SYNTHESIS STRATEGY:
    - Identify common themes and insights across sources
    - Combine complementary perspectives
    - Extract practical advice for SMB owners
    - Organize into logical, accessible structure
    - Add actionable takeaways

    PARAMETERS:
        client: Authenticated Anthropic client
        topic_name: Name of the topic being synthesized
        articles: List of article dictionaries from database
        model: Claude model to use (default: sonnet-4.5)

    RETURNS:
        str: Generated article content in Markdown format

    MODEL OPTIONS:
        - "claude-sonnet-4-5-20250929": Best quality, balanced cost (~$0.12/article)
        - "claude-haiku-4-5-20251001": Fast and cheap (~$0.01/article)

    COST PER CALL:
        Sonnet 4.5 (30K input, 2K output): ~$0.12
        Haiku 4.5 (30K input, 2K output): ~$0.01
    """

    # CONSTRUCT SOURCE ARTICLES SECTION
    # Format each article with clear delimiters for Claude
    source_articles_text = ""
    for i, article in enumerate(articles, 1):
        source_articles_text += f"""
---
SOURCE ARTICLE {i}
Title: {article['title']}
Source: {article['source']}
Published: {article.get('published_date', 'Unknown')}
URL: {article['url']}

Content:
{article['content']}
---

"""

    # CONSTRUCT SMB-FOCUSED SYNTHESIS PROMPT
    # This prompt emphasizes practical value for small business owners
    prompt = f"""You are a legal content writer specializing in making Canadian legal topics accessible to small and medium-sized business (SMB) owners.

Your task: Synthesize the following {len(articles)} legal articles about "{topic_name}" into ONE comprehensive article for SMB owners.

SYNTHESIS REQUIREMENTS:

1. **Target Audience**: Canadian SMB owners (10-500 employees) with no legal background
   - Explain legal concepts in plain language
   - Focus on practical implications, not theory
   - Assume reader needs actionable guidance

2. **Content Strategy**:
   - Identify 3-5 key themes across the source articles
   - Combine complementary perspectives from different sources
   - Resolve any contradictions by explaining context
   - Extract practical takeaways and action items
   - Include real-world examples when available

3. **Structure** (use this format):
   - Opening: Why this topic matters for SMBs (2-3 paragraphs)
   - Key Insights: 3-5 main themes with explanations
   - Practical Implications: What this means for your business
   - Action Items: Concrete steps SMBs should take
   - Resources: Where to get help (lawyers, government resources)

4. **Tone & Style**:
   - Professional but conversational
   - Authoritative but not condescending
   - Clear and direct (no legal jargon without explanation)
   - Use "you/your" to address the reader
   - Active voice preferred

5. **Length**: Aim for 1500-2000 words (comprehensive but readable)

6. **Citations**: When referencing specific cases, legislation, or facts, mention the source article informally (e.g., "According to analysis from Monkhouse Law..." or "As noted in recent commentary...")

SOURCE ARTICLES:
{source_articles_text}

Write the synthesized article now. Output in Markdown format with clear headings (# for title, ## for sections, ### for subsections).

Begin with the article title as # heading, then write the full article."""

    # CALL CLAUDE API
    logger.info(f"Sending {len(articles)} articles to Claude for synthesis...")
    logger.info(f"Using model: {model}")

    response = client.messages.create(
        model=model,
        max_tokens=4096,  # Enough for 1500-2000 word article
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # EXTRACT GENERATED CONTENT
    # Claude's response is in response.content[0].text
    generated_content = response.content[0].text

    # LOG TOKEN USAGE FOR COST TRACKING
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    logger.info(f"✓ Article generated successfully")
    logger.info(f"  Input tokens: {input_tokens:,}")
    logger.info(f"  Output tokens: {output_tokens:,}")

    # CALCULATE COST
    # Pricing as of January 2026
    if "sonnet" in model.lower():
        input_cost = (input_tokens / 1_000_000) * 3.00
        output_cost = (output_tokens / 1_000_000) * 15.00
    elif "haiku" in model.lower():
        input_cost = (input_tokens / 1_000_000) * 0.25
        output_cost = (output_tokens / 1_000_000) * 1.25
    else:
        input_cost = 0
        output_cost = 0

    total_cost = input_cost + output_cost
    logger.info(f"  Estimated cost: ${total_cost:.4f}")

    return generated_content


# ============================================================================
# FILE OUTPUT
# ============================================================================

def save_generated_article(
    topic_name: str,
    content: str,
    articles: List[Dict],
    model: str,
    output_dir: str = "output/generated_articles"
) -> str:
    """
    Save generated article to file with metadata.

    WHAT THIS DOES:
    1. Creates output directory if needed
    2. Generates filename from topic name and date
    3. Adds metadata header (topic, date, sources, model, word count)
    4. Saves to Markdown file

    PARAMETERS:
        topic_name: Name of the topic
        content: Generated article content
        articles: Source articles used for synthesis
        model: Claude model used
        output_dir: Directory to save files (default: output/generated_articles)

    RETURNS:
        str: Path to saved file

    OUTPUT FILE STRUCTURE:
        output/
        └── generated_articles/
            ├── employment_law_2026_01_20.md
            ├── contract_law_2026_01_21.md
            └── privacy_law_2026_01_22.md

    FILE FORMAT:
        ---
        topic: Employment Law
        generated_date: 2026-01-20T14:30:00
        source_count: 5
        model: claude-sonnet-4-5-20250929
        word_count: 1842
        sources:
          - title: "Article 1"
            url: https://...
          - title: "Article 2"
            url: https://...
        ---

        [Generated content...]
    """

    # CREATE OUTPUT DIRECTORY
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # GENERATE FILENAME
    # Convert topic name to filename-safe format
    # "Employment Law" → "employment_law"
    safe_topic = topic_name.lower().replace(' ', '_').replace('/', '_')
    safe_topic = ''.join(c for c in safe_topic if c.isalnum() or c == '_')

    # Add date to filename for uniqueness
    date_str = datetime.now().strftime('%Y_%m_%d')
    filename = f"{safe_topic}_{date_str}.md"
    filepath = os.path.join(output_dir, filename)

    # CALCULATE WORD COUNT
    word_count = len(content.split())

    # BUILD METADATA HEADER
    # Using YAML frontmatter format (common for Markdown processors)
    metadata = f"""---
topic: {topic_name}
generated_date: {datetime.now().isoformat()}
source_count: {len(articles)}
model: {model}
word_count: {word_count}
sources:
"""

    # ADD SOURCE LIST TO METADATA
    for article in articles:
        metadata += f"""  - title: "{article['title']}"
    source: {article['source']}
    url: {article['url']}
"""

    metadata += "---\n\n"

    # COMBINE METADATA AND CONTENT
    full_content = metadata + content

    # WRITE TO FILE
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(full_content)

    logger.info(f"✓ Article saved to: {filepath}")
    logger.info(f"  Word count: {word_count:,}")

    return filepath


# ============================================================================
# GENERATION ORCHESTRATION
# ============================================================================

def generate_article_for_topics(
    db: Database,
    client: Anthropic,
    topic_ids: List[int],
    model: str = "claude-sonnet-4-5-20250929",
    combined_title: Optional[str] = None
) -> Optional[str]:
    """
    Generate a synthesized article from multiple topics (subtopics).

    WHAT THIS DOES:
    1. Fetch articles for all specified topic IDs
    2. Combine articles from multiple topics
    3. Generate comprehensive article using Claude
    4. Save to file with combined topic name

    PARAMETERS:
        db: Database instance
        client: Authenticated Anthropic client
        topic_ids: List of topic IDs to combine
        model: Claude model to use
        combined_title: Optional custom title for combined article

    RETURNS:
        str: Path to saved article file, or None if generation failed

    USE CASES:
        - Combine multiple subtopics under same parent
        - Generate comprehensive overview across related topics
    """

    # FETCH ALL ARTICLES FOR ALL TOPICS
    all_articles = []
    topic_names = []

    for topic_id in topic_ids:
        topic = db.get_topic_by_id(topic_id)
        if not topic:
            logger.warning(f"Topic ID {topic_id} not found, skipping")
            continue

        topic_names.append(topic['topic_name'])
        articles = db.get_articles_for_topic(topic_id)

        # Filter for articles with content
        articles_with_content = [a for a in articles if a.get('content') and len(a['content']) > 100]
        all_articles.extend(articles_with_content)

    if not all_articles:
        logger.error("No articles with substantial content found across specified topics")
        return None

    # DEDUPLICATE ARTICLES (in case same article tagged with multiple subtopics)
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article['url'] not in seen_urls:
            seen_urls.add(article['url'])
            unique_articles.append(article)

    logger.info(f"Found {len(unique_articles)} unique articles across {len(topic_ids)} topics")

    # CREATE COMBINED TOPIC NAME
    if combined_title:
        topic_name = combined_title
    elif len(topic_names) == 1:
        topic_name = topic_names[0]
    else:
        # Combine topic names (limit to avoid too long titles)
        if len(topic_names) <= 3:
            topic_name = " & ".join(topic_names)
        else:
            topic_name = f"{topic_names[0]} and {len(topic_names)-1} related topics"

    # SYNTHESIZE WITH CLAUDE
    try:
        generated_content = synthesize_articles(client, topic_name, unique_articles, model)
    except Exception as e:
        logger.error(f"Failed to synthesize articles: {e}")
        return None

    # SAVE TO FILE
    try:
        filepath = save_generated_article(topic_name, generated_content, unique_articles, model)

        # TRACK GENERATION FOR EACH TOPIC
        word_count = len(generated_content.split())
        for topic_id in topic_ids:
            db.track_generation(
                topic_id=topic_id,
                output_file=filepath,
                model_used=model,
                source_article_count=len(unique_articles),
                word_count=word_count
            )

        return filepath
    except Exception as e:
        logger.error(f"Failed to save generated article: {e}")
        return None


def generate_article_for_topic(
    db: Database,
    client: Anthropic,
    topic_id: int,
    model: str = "claude-sonnet-4-5-20250929"
) -> Optional[str]:
    """
    Generate a synthesized article for a specific topic.

    WHAT THIS DOES:
    1. Fetch topic information from database
    2. Fetch all articles for that topic
    3. Validate sufficient source material
    4. Call Claude to synthesize articles
    5. Save generated article to file
    6. Return path to saved file

    PARAMETERS:
        db: Database instance
        client: Authenticated Anthropic client
        topic_id: ID of topic to generate article for
        model: Claude model to use

    RETURNS:
        str: Path to saved article file, or None if generation failed

    VALIDATION:
        - Topic must exist
        - Topic must have at least 1 article (ideally 2+)
        - Articles must have substantial content

    SPECIAL HANDLING:
        - If topic is a parent, generates from all subtopics combined
        - If topic is a subtopic, generates from that subtopic only
    """

    # FETCH TOPIC INFO
    topic = db.get_topic_by_id(topic_id)
    if not topic:
        logger.error(f"Topic ID {topic_id} not found in database")
        return None

    topic_name = topic['topic_name']
    is_parent = topic.get('is_parent', 0) == 1

    # HANDLE PARENT TOPICS
    if is_parent:
        logger.info(f"Topic '{topic_name}' is a parent topic. Generating from all subtopics...")
        subtopics = db.get_subtopics_for_parent(topic_id)

        if not subtopics:
            logger.error(f"Parent topic '{topic_name}' has no subtopics")
            return None

        subtopic_ids = [st['id'] for st in subtopics]
        logger.info(f"Found {len(subtopic_ids)} subtopics under '{topic_name}'")

        # Generate combined article from all subtopics
        return generate_article_for_topics(db, client, subtopic_ids, model, combined_title=topic_name)

    # HANDLE REGULAR SUBTOPICS
    logger.info(f"Generating article for topic: {topic_name} (ID: {topic_id})")

    # FETCH ARTICLES FOR TOPIC
    articles = db.get_articles_for_topic(topic_id)

    if not articles:
        logger.error(f"No articles found for topic '{topic_name}'")
        return None

    logger.info(f"Found {len(articles)} source articles")

    # VALIDATE ARTICLE QUALITY
    # Check that articles have substantial content
    articles_with_content = [a for a in articles if a.get('content') and len(a['content']) > 100]

    if not articles_with_content:
        logger.error(f"No articles with substantial content for topic '{topic_name}'")
        return None

    if len(articles_with_content) < len(articles):
        logger.warning(f"Only {len(articles_with_content)}/{len(articles)} articles have substantial content")
        articles = articles_with_content

    # SYNTHESIZE WITH CLAUDE
    try:
        generated_content = synthesize_articles(client, topic_name, articles, model)
    except Exception as e:
        logger.error(f"Failed to synthesize articles: {e}")
        return None

    # SAVE TO FILE
    try:
        filepath = save_generated_article(topic_name, generated_content, articles, model)

        # TRACK GENERATION IN DATABASE
        word_count = len(generated_content.split())
        db.track_generation(
            topic_id=topic_id,
            output_file=filepath,
            model_used=model,
            source_article_count=len(articles),
            word_count=word_count
        )

        return filepath
    except Exception as e:
        logger.error(f"Failed to save generated article: {e}")
        return None


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def generate_article_from_custom_articles(
    db: Database,
    client: Anthropic,
    custom_articles_file: str,
    model: str = "claude-sonnet-4-5-20250929"
) -> Optional[str]:
    """
    Generate article from custom-selected articles (used by Streamlit UI).

    WHAT THIS DOES:
    1. Load JSON file with article IDs and metadata
    2. Fetch specified articles from database
    3. Generate article using Claude
    4. Save to file with custom or default topic name

    PARAMETERS:
        db: Database instance
        client: Authenticated Anthropic client
        custom_articles_file: Path to JSON file with article selection
        model: Claude model to use

    JSON FILE FORMAT:
        {
            "article_ids": [1, 2, 3],
            "topic_name": "Custom Topic Name",
            "topic_id": 5
        }

    RETURNS:
        str: Path to saved article file, or None if generation failed
    """
    import json

    # LOAD CUSTOM ARTICLES CONFIGURATION
    try:
        with open(custom_articles_file, 'r') as f:
            config = json.load(f)

        article_ids = config.get('article_ids', [])
        topic_name = config.get('topic_name', 'Custom Article')
        topic_id = config.get('topic_id')

        if not article_ids:
            logger.error("No article IDs provided in custom articles file")
            return None

        logger.info(f"Loading {len(article_ids)} custom-selected articles")

    except FileNotFoundError:
        logger.error(f"Custom articles file not found: {custom_articles_file}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in custom articles file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading custom articles file: {e}")
        return None

    # FETCH ARTICLES FROM DATABASE
    articles = []
    for article_id in article_ids:
        article = db.get_article_by_id(article_id)
        if article:
            articles.append(article)
        else:
            logger.warning(f"Article ID {article_id} not found in database")

    if not articles:
        logger.error("No valid articles found for custom selection")
        return None

    logger.info(f"Successfully loaded {len(articles)} articles")

    # VALIDATE ARTICLE QUALITY
    articles_with_content = [a for a in articles if a.get('content') and len(a['content']) > 100]

    if not articles_with_content:
        logger.error("No articles with substantial content in selection")
        return None

    if len(articles_with_content) < len(articles):
        logger.warning(f"Only {len(articles_with_content)}/{len(articles)} articles have substantial content")
        articles = articles_with_content

    # SYNTHESIZE WITH CLAUDE
    try:
        generated_content = synthesize_articles(client, topic_name, articles, model)
    except Exception as e:
        logger.error(f"Failed to synthesize articles: {e}")
        return None

    # SAVE TO FILE
    try:
        filepath = save_generated_article(topic_name, generated_content, articles, model)

        # TRACK GENERATION IN DATABASE (if topic_id provided)
        if topic_id:
            word_count = len(generated_content.split())
            db.track_generation(
                topic_id=topic_id,
                output_file=filepath,
                model_used=model,
                source_article_count=len(articles),
                word_count=word_count
            )

        return filepath
    except Exception as e:
        logger.error(f"Failed to save generated article: {e}")
        return None


def parse_arguments():
    """
    Parse command-line arguments.

    WHAT THIS DOES:
    Defines CLI interface for flexible generation options.

    USAGE EXAMPLES:
        python generate.py --topic 5
        python generate.py --topics 5 12 8 15
        python generate.py --topics-file topics_to_generate.txt
        python generate.py --topic 5 --model haiku
    """
    parser = argparse.ArgumentParser(
        description="Generate synthesized articles from collected legal news",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate.py --topic 5
  python generate.py --topics 5 12 8
  python generate.py --topics-file topics_to_generate.txt
  python generate.py --topic 5 --model haiku
        """
    )

    # TOPIC SELECTION OPTIONS
    # User can specify topics in multiple ways:
    # - Single topic ID (subtopic or parent)
    # - Multiple topic IDs
    # - Topic IDs from file
    # - Parent topic (generates from all subtopics)
    # - Multiple subtopics
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--topic',
        type=int,
        help='Generate article for single topic ID (subtopic or parent)'
    )
    group.add_argument(
        '--topics',
        type=int,
        nargs='+',
        help='Generate articles for multiple topic IDs'
    )
    group.add_argument(
        '--parent',
        type=int,
        help='Generate comprehensive article from all subtopics under a parent topic'
    )
    group.add_argument(
        '--subtopics',
        type=int,
        nargs='+',
        help='Generate article combining specific subtopics'
    )
    group.add_argument(
        '--topics-file',
        type=str,
        help='File containing topic IDs (one per line)'
    )

    # MODEL SELECTION
    parser.add_argument(
        '--model',
        type=str,
        choices=['sonnet', 'haiku'],
        default='sonnet',
        help='Claude model to use (default: sonnet)'
    )

    # CUSTOM ARTICLES (used by Streamlit UI)
    parser.add_argument(
        '--custom-articles',
        type=str,
        help='JSON file with custom article selection (for Streamlit UI)'
    )

    return parser.parse_args()


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main():
    """
    Main function to orchestrate article generation.

    WHAT THIS DOES:
    1. Parse command-line arguments
    2. Initialize database and Claude client
    3. Determine which topics to process
    4. Generate article for each topic
    5. Report statistics
    """

    logger.info("=" * 80)
    logger.info("STARTING ARTICLE GENERATION")
    logger.info("=" * 80)

    # ENSURE OUTPUT DIRECTORY EXISTS
    os.makedirs('logs', exist_ok=True)
    os.makedirs('output/generated_articles', exist_ok=True)

    # PARSE ARGUMENTS
    args = parse_arguments()

    # MAP MODEL CHOICE TO FULL MODEL NAME
    if args.model == 'sonnet':
        model = "claude-sonnet-4-5-20250929"
        logger.info("Using Claude Sonnet 4.5 (best quality, ~$0.12/article)")
    else:  # haiku
        model = "claude-haiku-4-5-20251001"
        logger.info("Using Claude Haiku 4.5 (fast & cheap, ~$0.01/article)")

    # INITIALIZE DATABASE AND CLAUDE CLIENT
    db = Database()

    try:
        client = initialize_claude_client()
    except ValueError as e:
        logger.error(f"Failed to initialize Claude client: {e}")
        db.close()
        return

    # HANDLE CUSTOM ARTICLES (Streamlit UI feature)
    if args.custom_articles:
        logger.info(f"Processing custom article selection from {args.custom_articles}")

        try:
            filepath = generate_article_from_custom_articles(db, client, args.custom_articles, model)

            if filepath:
                logger.info(f"\n✅ Generated article from custom selection: {filepath}")
            else:
                logger.error("Failed to generate article from custom selection")

            db.close()
            return

        except Exception as e:
            logger.error(f"Error generating article from custom selection: {e}")
            db.close()
            return

    # DETERMINE TOPIC IDS TO PROCESS
    if args.topic:
        topic_ids = [args.topic]
    elif args.topics:
        topic_ids = args.topics
    elif args.parent:
        # GENERATE FROM ALL SUBTOPICS UNDER PARENT
        logger.info(f"Generating article from parent topic ID {args.parent}")
        parent_topic = db.get_topic_by_id(args.parent)

        if not parent_topic:
            logger.error(f"Parent topic ID {args.parent} not found")
            db.close()
            return

        if parent_topic.get('is_parent', 0) != 1:
            logger.error(f"Topic ID {args.parent} is not a parent topic")
            db.close()
            return

        # Get all subtopics and use generate_article_for_topic which handles parents
        topic_ids = [args.parent]

    elif args.subtopics:
        # COMBINE SPECIFIC SUBTOPICS INTO ONE ARTICLE
        logger.info(f"Combining {len(args.subtopics)} subtopics into single article")

        try:
            filepath = generate_article_for_topics(db, client, args.subtopics, model)

            if filepath:
                logger.info(f"\n✅ Generated combined article: {filepath}")
            else:
                logger.error("Failed to generate combined article")

            db.close()
            return

        except Exception as e:
            logger.error(f"Error generating combined article: {e}")
            db.close()
            return

    elif args.topics_file:
        # READ TOPIC IDS FROM FILE
        try:
            with open(args.topics_file, 'r') as f:
                topic_ids = [int(line.strip()) for line in f if line.strip().isdigit()]
            logger.info(f"Loaded {len(topic_ids)} topic IDs from {args.topics_file}")
        except FileNotFoundError:
            logger.error(f"Topics file not found: {args.topics_file}")
            db.close()
            return
        except Exception as e:
            logger.error(f"Error reading topics file: {e}")
            db.close()
            return
    else:
        topic_ids = []

    if not topic_ids:
        logger.error("No valid topic IDs provided")
        db.close()
        return

    logger.info(f"Processing {len(topic_ids)} topics...")

    # GENERATE ARTICLES
    successful = 0
    failed = 0
    generated_files = []

    for topic_id in topic_ids:
        logger.info(f"\nProcessing topic ID {topic_id}...")

        try:
            filepath = generate_article_for_topic(db, client, topic_id, model)

            if filepath:
                successful += 1
                generated_files.append(filepath)
            else:
                failed += 1

        except Exception as e:
            logger.error(f"Unexpected error processing topic {topic_id}: {e}")
            failed += 1

    # REPORT FINAL STATISTICS
    logger.info("=" * 80)
    logger.info("ARTICLE GENERATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total topics processed: {len(topic_ids)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")

    if generated_files:
        logger.info(f"\nGenerated articles:")
        for filepath in generated_files:
            logger.info(f"  - {filepath}")

    # CLOSE DATABASE
    db.close()


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Entry point when script is run directly.

    USAGE:
        python generate.py --topic 5
        python generate.py --topics 5 12 8
        python generate.py --topics-file topics_to_generate.txt

    PREREQUISITES:
        1. .env file with ANTHROPIC_API_KEY set
        2. Database with topics and articles (run compile.py first)
        3. Topics selected for generation (use view_topics.py)

    WHAT HAPPENS:
        - Processes specified topics
        - Generates synthesized articles with Claude
        - Saves to output/generated_articles/
        - Logs all activities to logs/generate.log
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user. Progress has been saved.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
