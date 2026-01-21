"""
================================================================================
MAIN.PY - PHASE 7: PIPELINE ORCHESTRATION
================================================================================

PURPOSE:
This module orchestrates the entire legal news pipeline from end to end,
running all phases in sequence: fetch → compile → generate.

WHAT THIS MODULE DOES:
1. Fetch new articles from configured sources (fetch.py)
2. Extract topics from unprocessed articles (compile.py)
3. Generate synthesized articles for selected topics (generate.py)
4. Report comprehensive statistics and status

WHY WE NEED THIS:
Instead of running each script manually, main.py provides:
- One-command pipeline execution
- Automated workflow for scheduled runs
- Consistent logging and error handling
- Progress tracking across all phases
- Summary reports

USE CASES:
- Daily automated pipeline run (via cron/scheduled task)
- Manual full pipeline execution
- CI/CD integration for testing
- Batch processing of accumulated articles

WORKFLOW:
1. FETCH PHASE: Collect new articles from RSS feeds, APIs, and web scraping
2. COMPILE PHASE: Extract topics from unprocessed articles with Gemini AI
3. GENERATE PHASE: Synthesize articles for high-value topics with Claude
4. REPORT: Show summary of work done

USAGE:
    # Run full pipeline with defaults
    python main.py

    # Run specific phases only
    python main.py --skip-fetch    # Skip fetching, process existing articles
    python main.py --skip-generate # Fetch and compile only

    # Auto-generate for high-value topics
    python main.py --auto-generate --min-score 8 --min-articles 3

DEPENDENCIES:
    - All previous phase modules (fetch.py, compile.py, generate.py)
    - Environment variables for API keys

================================================================================
"""

import os
import sys
import argparse
import logging
import subprocess
from datetime import datetime
from typing import Dict, List
from database import Database


# CONFIGURE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/main.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# PIPELINE PHASES
# ============================================================================

def run_fetch_phase() -> bool:
    """
    Run Phase 1: Article collection.

    WHAT THIS DOES:
    Executes fetch.py to collect new articles from configured sources.

    RETURNS:
        bool: True if successful, False otherwise
    """
    logger.info("=" * 80)
    logger.info("PHASE 1: FETCHING ARTICLES")
    logger.info("=" * 80)

    try:
        # RUN FETCH.PY AS SUBPROCESS
        # We use subprocess instead of importing to ensure clean execution
        result = subprocess.run(
            [sys.executable, 'fetch.py'],
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        # CHECK EXIT CODE
        if result.returncode == 0:
            logger.info("✓ Fetch phase completed successfully")
            return True
        else:
            logger.error(f"✗ Fetch phase failed with exit code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("✗ Fetch phase timed out after 10 minutes")
        return False
    except Exception as e:
        logger.error(f"✗ Fetch phase failed: {e}")
        return False


def run_compile_phase() -> bool:
    """
    Run Phase 4: Topic extraction.

    WHAT THIS DOES:
    Executes compile.py to extract topics from unprocessed articles.

    NOTE ON RATE LIMITS:
    If Gemini rate limit is hit, this is not considered a failure.
    Partially processed articles are saved and will continue next run.

    RETURNS:
        bool: True if successful (even if rate limited), False on hard error
    """
    logger.info("=" * 80)
    logger.info("PHASE 4: EXTRACTING TOPICS")
    logger.info("=" * 80)

    try:
        # RUN COMPILE.PY AS SUBPROCESS
        result = subprocess.run(
            [sys.executable, 'compile.py'],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout (for large batches)
        )

        # CHECK EXIT CODE
        if result.returncode == 0:
            logger.info("✓ Compile phase completed successfully")
            return True
        else:
            # CHECK IF IT'S A RATE LIMIT (not a hard failure)
            if "RESOURCE_EXHAUSTED" in result.stderr or "rate limit" in result.stderr.lower():
                logger.warning("⚠ Compile phase hit rate limit (this is normal)")
                logger.info("  Processed articles saved. Run again tomorrow to continue.")
                return True  # Not a failure, just quota reached
            else:
                logger.error(f"✗ Compile phase failed with exit code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                return False

    except subprocess.TimeoutExpired:
        logger.error("✗ Compile phase timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"✗ Compile phase failed: {e}")
        return False


def run_generate_phase(topic_ids: List[int] = None, model: str = 'sonnet') -> bool:
    """
    Run Phase 6: Article synthesis.

    WHAT THIS DOES:
    Executes generate.py to create synthesized articles for specified topics.

    PARAMETERS:
        topic_ids: List of topic IDs to generate articles for
                  If None, generation phase is skipped
        model: Claude model to use ('sonnet' or 'haiku')

    RETURNS:
        bool: True if successful, False otherwise
    """
    if not topic_ids:
        logger.info("No topics specified for generation phase (skipping)")
        return True

    logger.info("=" * 80)
    logger.info("PHASE 6: GENERATING ARTICLES")
    logger.info("=" * 80)

    try:
        # BUILD COMMAND
        cmd = [sys.executable, 'generate.py', '--topics'] + [str(tid) for tid in topic_ids]
        cmd.extend(['--model', model])

        # RUN GENERATE.PY AS SUBPROCESS
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )

        # CHECK EXIT CODE
        if result.returncode == 0:
            logger.info(f"✓ Generate phase completed successfully ({len(topic_ids)} topics)")
            return True
        else:
            logger.error(f"✗ Generate phase failed with exit code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("✗ Generate phase timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"✗ Generate phase failed: {e}")
        return False


# ============================================================================
# AUTO-GENERATION LOGIC
# ============================================================================

def select_topics_for_auto_generation(
    db: Database,
    min_score: int = 8,
    min_articles: int = 3,
    max_topics: int = 5
) -> List[int]:
    """
    Automatically select high-value topics for article generation.

    WHAT THIS DOES:
    Applies filters to identify topics worth generating articles for,
    prioritizing high SMB relevance and good source coverage.

    SELECTION CRITERIA:
    - SMB relevance score >= min_score (default: 8/10)
    - Article count >= min_articles (default: 3)
    - Sort by article count descending
    - Limit to max_topics (default: 5 to control costs)

    PARAMETERS:
        db: Database instance
        min_score: Minimum SMB relevance score (0-10)
        min_articles: Minimum number of source articles
        max_topics: Maximum number of topics to generate

    RETURNS:
        List[int]: List of topic IDs selected for generation

    EXAMPLE:
        topics = select_topics_for_auto_generation(db, min_score=8, min_articles=3, max_topics=5)
        # Returns: [12, 5, 18, 22, 9] (top 5 topics meeting criteria)
    """
    logger.info(f"Auto-selecting topics (score >= {min_score}, articles >= {min_articles})")

    # GET ALL TOPICS WITH METADATA
    all_topics = db.get_topics_with_metadata()

    if not all_topics:
        logger.warning("No topics found in database")
        return []

    # FILTER BY CRITERIA
    filtered = [
        t for t in all_topics
        if t.get('smb_relevance_score', 0) >= min_score
        and t.get('article_count', 0) >= min_articles
    ]

    if not filtered:
        logger.warning(f"No topics match criteria (score >= {min_score}, articles >= {min_articles})")
        return []

    # SORT BY ARTICLE COUNT (most articles first)
    # This prioritizes topics with better source coverage
    filtered.sort(key=lambda t: t.get('article_count', 0), reverse=True)

    # LIMIT TO MAX_TOPICS
    selected = filtered[:max_topics]

    # EXTRACT TOPIC IDS
    topic_ids = [t['id'] for t in selected]

    logger.info(f"Selected {len(topic_ids)} topics for generation:")
    for topic in selected:
        logger.info(f"  - {topic['topic_name']} (score: {topic['smb_relevance_score']}, articles: {topic['article_count']})")

    return topic_ids


# ============================================================================
# REPORTING
# ============================================================================

def print_pipeline_summary(db: Database):
    """
    Print comprehensive pipeline status summary.

    WHAT THIS DOES:
    Shows current state of the pipeline: articles, topics, generated content.
    """
    logger.info("=" * 80)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 80)

    # GET DATABASE STATS
    stats = db.get_stats()

    logger.info(f"Articles:         {stats['total_articles']} total, {stats['unprocessed_articles']} unprocessed")
    logger.info(f"Topics:           {stats['total_topics']} unique topics")
    logger.info(f"Article-Topic Links: {stats['total_links']} relationships")

    # COUNT GENERATED ARTICLES
    output_dir = 'output/generated_articles'
    if os.path.exists(output_dir):
        generated_count = len([f for f in os.listdir(output_dir) if f.endswith('.md')])
        logger.info(f"Generated Articles: {generated_count} files in {output_dir}")
    else:
        logger.info(f"Generated Articles: 0 (directory not yet created)")

    # SHOW TOP TOPICS
    topics = db.get_topics_with_metadata()
    if topics:
        sorted_topics = sorted(topics, key=lambda t: t.get('article_count', 0), reverse=True)[:5]
        logger.info(f"\nTop 5 Topics by Coverage:")
        for i, topic in enumerate(sorted_topics, 1):
            logger.info(f"  {i}. {topic['topic_name']} - {topic['article_count']} articles (SMB: {topic['smb_relevance_score']}/10)")

    logger.info("=" * 80)


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the complete legal news pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline
  python main.py

  # Skip fetching (process existing articles)
  python main.py --skip-fetch

  # Auto-generate for high-value topics
  python main.py --auto-generate --min-score 8 --min-articles 3

  # Use Claude Haiku for generation (cheaper)
  python main.py --auto-generate --model haiku
        """
    )

    # PHASE CONTROL
    parser.add_argument(
        '--skip-fetch',
        action='store_true',
        help='Skip article fetching phase'
    )
    parser.add_argument(
        '--skip-compile',
        action='store_true',
        help='Skip topic extraction phase'
    )
    parser.add_argument(
        '--skip-generate',
        action='store_true',
        help='Skip article generation phase'
    )

    # AUTO-GENERATION OPTIONS
    parser.add_argument(
        '--auto-generate',
        action='store_true',
        help='Automatically select and generate articles for high-value topics'
    )
    parser.add_argument(
        '--min-score',
        type=int,
        default=8,
        help='Minimum SMB relevance score for auto-generation (default: 8)'
    )
    parser.add_argument(
        '--min-articles',
        type=int,
        default=3,
        help='Minimum article count for auto-generation (default: 3)'
    )
    parser.add_argument(
        '--max-topics',
        type=int,
        default=5,
        help='Maximum topics to generate (default: 5)'
    )

    # MODEL SELECTION
    parser.add_argument(
        '--model',
        choices=['sonnet', 'haiku'],
        default='sonnet',
        help='Claude model for generation (default: sonnet)'
    )

    return parser.parse_args()


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main():
    """
    Main pipeline orchestration function.

    WHAT THIS DOES:
    1. Parse arguments
    2. Run enabled phases in sequence
    3. Generate articles if requested
    4. Print summary report
    """

    # ENSURE DIRECTORIES EXIST
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('output/generated_articles', exist_ok=True)

    logger.info("=" * 80)
    logger.info("CANADIAN LEGAL NEWS PIPELINE")
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    # PARSE ARGUMENTS
    args = parse_arguments()

    # TRACK SUCCESS/FAILURE
    phases_run = []
    phases_failed = []

    # INITIALIZE DATABASE
    db = Database()

    # PHASE 1: FETCH
    if not args.skip_fetch:
        success = run_fetch_phase()
        phases_run.append('fetch')
        if not success:
            phases_failed.append('fetch')
            logger.error("Fetch phase failed. Stopping pipeline.")
            db.close()
            return
    else:
        logger.info("Skipping fetch phase (--skip-fetch)")

    # PHASE 4: COMPILE
    if not args.skip_compile:
        success = run_compile_phase()
        phases_run.append('compile')
        if not success:
            phases_failed.append('compile')
            logger.error("Compile phase failed. Stopping pipeline.")
            db.close()
            return
    else:
        logger.info("Skipping compile phase (--skip-compile)")

    # PHASE 6: GENERATE
    if not args.skip_generate:
        topic_ids = None

        # DETERMINE TOPICS TO GENERATE
        if args.auto_generate:
            topic_ids = select_topics_for_auto_generation(
                db,
                min_score=args.min_score,
                min_articles=args.min_articles,
                max_topics=args.max_topics
            )

        if topic_ids:
            success = run_generate_phase(topic_ids, model=args.model)
            phases_run.append('generate')
            if not success:
                phases_failed.append('generate')
        else:
            logger.info("No topics selected for generation (use --auto-generate or run generate.py manually)")
    else:
        logger.info("Skipping generate phase (--skip-generate)")

    # PRINT FINAL SUMMARY
    print_pipeline_summary(db)

    # REPORT PHASE RESULTS
    logger.info(f"\nPhases executed: {', '.join(phases_run)}")
    if phases_failed:
        logger.error(f"Phases failed: {', '.join(phases_failed)}")
    else:
        logger.info("✓ All phases completed successfully!")

    logger.info(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # CLOSE DATABASE
    db.close()


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Entry point when script is run directly.

    USAGE:
        python main.py

    PREREQUISITES:
        1. All environment variables configured in .env
        2. Virtual environment with all dependencies installed
        3. Database initialized (happens automatically)

    WHAT HAPPENS:
        - Runs full pipeline (fetch → compile → generate)
        - Handles errors gracefully
        - Logs everything to logs/main.log
    """
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed with unexpected error: {e}", exc_info=True)
        raise
