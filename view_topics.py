"""
================================================================================
VIEW_TOPICS.PY - PHASE 5: INTERACTIVE TOPIC BROWSER
================================================================================

PURPOSE:
This module provides an interactive command-line interface (CLI) for exploring
extracted legal topics and selecting which ones to synthesize into articles.

WHAT THIS MODULE DOES:
1. Displays all extracted topics with statistics (article count, SMB score, dates)
2. Allows filtering by SMB relevance score (e.g., show only score >= 8)
3. Allows sorting by various criteria (article count, date, score)
4. Shows detailed view of articles for a specific topic
5. Exports topic lists for article generation

WHY WE NEED THIS:
After compile.py extracts topics from articles, we need a way to:
- Review what topics were identified
- Understand which topics have the most coverage
- Select high-value topics for article synthesis
- See which articles will be used for synthesis

USE CASES:
- "Show me all topics with SMB score >= 8 and at least 3 articles"
- "What articles discuss Employment Law?"
- "Which topics should I generate articles for this week?"
- "Export a list of top 10 topics by article count"

WORKFLOW:
1. Run compile.py to extract topics → Database has topics + relationships
2. Run view_topics.py to browse topics → Interactive exploration
3. Select topics for synthesis → Note topic IDs
4. Run generate.py with selected topics → Create synthesized articles

INTERFACE DESIGN:
This is a simple menu-driven CLI (no external dependencies like click or typer).
We use standard input() for simplicity and portability.

USAGE:
    python view_topics.py

DEPENDENCIES:
    - database.py (our Database class)
    - No external CLI libraries needed (just standard library)

================================================================================
"""

import os
from typing import List, Dict, Optional
from datetime import datetime
from database import Database


# ============================================================================
# DISPLAY HELPERS
# ============================================================================
# These functions format and display data in a user-friendly way

def clear_screen():
    """
    Clear the terminal screen for cleaner UI.

    WHAT THIS DOES:
    - On Unix/Mac: Runs 'clear' command
    - On Windows: Runs 'cls' command
    - Makes the interface less cluttered

    WHY WE USE THIS:
    When navigating menus, clearing the screen makes it easier to focus
    on current information without scrolling through previous output.
    """
    os.system('clear' if os.name != 'nt' else 'cls')


def print_header(title: str):
    """
    Print a formatted section header.

    EXAMPLE OUTPUT:
    ================================================================================
    TOPIC BROWSER
    ================================================================================
    """
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80 + "\n")


def print_topic_hierarchy(db: Database):
    """
    Display topics in hierarchical tree structure.

    WHAT THIS DOES:
    Shows parent topics with their subtopics indented underneath,
    creating a visual hierarchy.

    EXAMPLE OUTPUT:
    Employment Law (10/10 SMB) - 11 articles
    ├── Wrongful Dismissal (9/10) - 3 articles [ID: 2]
    ├── Harassment & Discrimination (9/10) - 4 articles [ID: 3]
    ├── Workplace Safety (9/10) - 2 articles [ID: 4]
    └── Employment Standards (9/10) - 2 articles [ID: 5]

    Contract Law (10/10 SMB) - 8 articles
    ├── Contract Formation (9/10) - 3 articles [ID: 6]
    ├── Breach of Contract (9/10) - 3 articles [ID: 7]
    └── Force Majeure (8/10) - 2 articles [ID: 8]
    """
    # GET PARENT TOPICS
    parent_topics = db.get_parent_topics()

    if not parent_topics:
        print("No parent topics found. Run compile.py with updated schema.")
        return

    print(f"\nTOPICS BY CATEGORY")
    print("=" * 80 + "\n")

    # DISPLAY EACH PARENT WITH SUBTOPICS
    for parent in parent_topics:
        parent_name = parent['topic_name']
        parent_score = parent.get('smb_relevance_score', 10)
        parent_id = parent['id']

        # Get subtopics for this parent
        subtopics = db.get_subtopics_for_parent(parent_id)

        # Calculate total articles (across all subtopics)
        total_articles = sum(st.get('article_count', 0) for st in subtopics)

        # Print parent topic
        print(f"{parent_name} ({parent_score}/10 SMB) - {total_articles} articles [ID: {parent_id}]")

        # Print subtopics with tree characters
        if subtopics:
            for i, subtopic in enumerate(subtopics):
                is_last = (i == len(subtopics) - 1)
                tree_char = "└──" if is_last else "├──"

                name = subtopic['topic_name']
                score = subtopic.get('smb_relevance_score', 'N/A')
                count = subtopic.get('article_count', 0)
                st_id = subtopic['id']

                print(f"{tree_char} {name} ({score}/10) - {count} articles [ID: {st_id}]")

        print()  # Blank line between parent topics

    print(f"Total: {len(parent_topics)} parent categories")


def print_topic_table(topics: List[Dict], show_dates: bool = True):
    """
    Display topics in a formatted table (flat view).

    WHAT THIS DOES:
    Prints a table of topics with their metadata, formatted for readability.
    This is the flat view (no hierarchy shown).

    TABLE COLUMNS:
    - ID: Database ID (used for selection)
    - Topic Name: The legal topic name
    - SMB Score: Relevance to SMBs (0-10)
    - Articles: Number of articles discussing this topic
    - Date Range: Earliest to latest article publication dates (optional)

    PARAMETERS:
        topics: List of topic dictionaries from Database
        show_dates: Whether to show date range column (default: True)

    EXAMPLE OUTPUT:
    ID  | Topic Name                    | SMB | Articles | Date Range
    ----|-------------------------------|-----|----------|------------------
    1   | Employment Law                | 9   | 5        | 2025-01-01 to 2025-01-15
    2   | Contract Law                  | 10  | 3        | 2025-01-05 to 2025-01-12
    """
    if not topics:
        print("No topics found.")
        return

    # PRINT TABLE HEADER
    if show_dates:
        print(f"{'ID':<4} | {'Topic Name':<45} | {'SMB':<3} | {'Articles':<8} | {'Date Range'}")
        print("-" * 4 + "-+-" + "-" * 45 + "-+-" + "-" * 3 + "-+-" + "-" * 8 + "-+-" + "-" * 30)
    else:
        print(f"{'ID':<4} | {'Topic Name':<45} | {'SMB':<3} | {'Articles':<8}")
        print("-" * 4 + "-+-" + "-" * 45 + "-+-" + "-" * 3 + "-+-" + "-" * 8)

    # PRINT TABLE ROWS
    for topic in topics:
        topic_id = topic['id']
        # Truncate long topic names to fit in column
        name = topic['topic_name'][:44] + "…" if len(topic['topic_name']) > 45 else topic['topic_name']
        score = topic.get('smb_relevance_score', 'N/A')
        count = topic.get('article_count', 0)

        if show_dates and topic.get('earliest_date'):
            # FORMAT DATE RANGE
            # Some topics might not have dates yet (if all articles lack published_date)
            earliest = topic.get('earliest_date', 'Unknown')[:10]  # Get just YYYY-MM-DD
            latest = topic.get('latest_date', 'Unknown')[:10]
            date_range = f"{earliest} to {latest}"
            print(f"{topic_id:<4} | {name:<45} | {score:<3} | {count:<8} | {date_range}")
        else:
            print(f"{topic_id:<4} | {name:<45} | {score:<3} | {count:<8}")

    print()  # Blank line after table


def print_articles_for_topic(db: Database, topic_id: int):
    """
    Display all articles linked to a specific topic.

    WHAT THIS DOES:
    Shows a detailed list of articles that discuss the selected topic,
    including title, source, date, and URL.

    PARAMETERS:
        db: Database instance
        topic_id: ID of the topic to show articles for

    EXAMPLE OUTPUT:
    Articles for: Employment Law (5 articles)
    ================================================================================

    1. New Employment Standards Coming in 2025
       Source: Monkhouse Law | Published: 2025-01-15
       URL: https://monkhouselaw.com/...
       Summary: Ontario introduces new employment standards...

    2. Wrongful Dismissal Case Analysis
       Source: Slaw | Published: 2025-01-12
       URL: https://slaw.ca/...
       Summary: Court rules in favor of employee...
    """
    # GET TOPIC INFO
    topic = db.get_topic_by_id(topic_id)
    if not topic:
        print(f"Topic ID {topic_id} not found.")
        return

    # GET ARTICLES
    articles = db.get_articles_for_topic(topic_id)

    # PRINT HEADER
    print(f"\nArticles for: {topic['topic_name']} ({len(articles)} articles)")
    print("=" * 80 + "\n")

    if not articles:
        print("No articles found for this topic.")
        return

    # PRINT EACH ARTICLE
    for i, article in enumerate(articles, 1):
        print(f"{i}. {article['title']}")
        print(f"   Source: {article['source']} | Published: {article.get('published_date', 'Unknown')[:10]}")
        print(f"   URL: {article['url']}")

        # SHOW SUMMARY IF AVAILABLE
        # Some articles might not have summaries
        if article.get('summary'):
            summary = article['summary'][:150]  # Truncate to 150 chars
            summary = summary + "..." if len(article['summary']) > 150 else summary
            print(f"   Summary: {summary}")

        print()  # Blank line between articles


# ============================================================================
# FILTERING AND SORTING
# ============================================================================

def filter_topics_by_score(topics: List[Dict], min_score: int) -> List[Dict]:
    """
    Filter topics to only those with SMB score >= min_score.

    WHAT THIS DOES:
    Returns only topics that meet the minimum SMB relevance threshold.

    USE CASE:
    If you only want to generate articles for highly-relevant topics,
    filter for score >= 8 to exclude moderately or low-relevant topics.

    PARAMETERS:
        topics: List of all topics
        min_score: Minimum SMB relevance score (0-10)

    RETURNS:
        Filtered list of topics

    EXAMPLE:
        all_topics = db.get_topics_with_metadata()
        high_value = filter_topics_by_score(all_topics, min_score=8)
        # Returns only topics with SMB score >= 8
    """
    return [t for t in topics if t.get('smb_relevance_score', 0) >= min_score]


def filter_topics_by_article_count(topics: List[Dict], min_articles: int) -> List[Dict]:
    """
    Filter topics to only those with at least min_articles articles.

    WHAT THIS DOES:
    Returns only topics that have enough source material for synthesis.

    WHY THIS MATTERS:
    - 1 article: Not enough perspectives for synthesis
    - 2-3 articles: Minimum for basic synthesis
    - 4+ articles: Ideal for comprehensive synthesis

    PARAMETERS:
        topics: List of all topics
        min_articles: Minimum number of articles required

    RETURNS:
        Filtered list of topics

    EXAMPLE:
        all_topics = db.get_topics_with_metadata()
        well_covered = filter_topics_by_article_count(all_topics, min_articles=3)
        # Returns only topics with 3+ articles
    """
    return [t for t in topics if t.get('article_count', 0) >= min_articles]


def sort_topics(topics: List[Dict], sort_by: str = 'article_count', reverse: bool = True) -> List[Dict]:
    """
    Sort topics by specified criteria.

    WHAT THIS DOES:
    Sorts topics to prioritize certain characteristics.

    SORT OPTIONS:
    - 'article_count': Most articles first (default)
    - 'smb_relevance_score': Highest SMB scores first
    - 'latest_date': Most recent topics first
    - 'topic_name': Alphabetical by name

    PARAMETERS:
        topics: List of topics to sort
        sort_by: Field to sort by
        reverse: True for descending (default), False for ascending

    RETURNS:
        Sorted list of topics

    EXAMPLE:
        # Get topics sorted by SMB score (highest first)
        sorted_topics = sort_topics(topics, sort_by='smb_relevance_score', reverse=True)
    """
    # HANDLE MISSING DATA
    # If a field is missing, use a default value for sorting
    # This prevents errors when sorting topics with incomplete data
    def safe_get(topic: Dict, key: str):
        """Get value with fallback for missing data"""
        if key == 'article_count':
            return topic.get(key, 0)
        elif key == 'smb_relevance_score':
            return topic.get(key, 0)
        elif key == 'latest_date':
            return topic.get(key, '1900-01-01')  # Very old date for missing values
        elif key == 'topic_name':
            return topic.get(key, '')
        else:
            return topic.get(key, '')

    return sorted(topics, key=lambda t: safe_get(t, sort_by), reverse=reverse)


# ============================================================================
# INTERACTIVE MENUS
# ============================================================================

def show_main_menu():
    """Display the main menu options."""
    print("\n" + "-" * 80)
    print("MAIN MENU")
    print("-" * 80)
    print("1. View topics by hierarchy (tree view)")
    print("2. View all topics (flat table)")
    print("3. Filter topics by SMB score")
    print("4. Filter topics by article count")
    print("5. View articles for a specific topic")
    print("6. Show database statistics")
    print("7. Export topic list (for generate.py)")
    print("8. Exit")
    print("-" * 80)


def view_hierarchy(db: Database):
    """
    Display topics in hierarchical tree view.

    WHAT THIS DOES:
    Shows parent topics with their subtopics indented underneath.
    """
    clear_screen()
    print_header("TOPIC HIERARCHY")

    print_topic_hierarchy(db)

    input("\nPress Enter to continue...")


def view_all_topics(db: Database):
    """
    Display all topics in flat table with options to sort.

    WHAT THIS DOES:
    Shows all topics (subtopics) in a flat table and allows sorting.
    """
    clear_screen()
    print_header("ALL TOPICS (FLAT VIEW)")

    # GET TOPICS WITH METADATA
    topics = db.get_topics_with_metadata()

    if not topics:
        print("No topics found. Run compile.py first to extract topics from articles.")
        input("\nPress Enter to continue...")
        return

    # ASK FOR SORT PREFERENCE
    print("Sort by:")
    print("1. Article count (default)")
    print("2. SMB relevance score")
    print("3. Most recent")
    print("4. Topic name (alphabetical)")

    choice = input("\nChoice (1-4, or Enter for default): ").strip()

    # APPLY SORTING
    if choice == '2':
        topics = sort_topics(topics, 'smb_relevance_score')
        print("\nSorted by SMB relevance score (highest first):")
    elif choice == '3':
        topics = sort_topics(topics, 'latest_date')
        print("\nSorted by most recent:")
    elif choice == '4':
        topics = sort_topics(topics, 'topic_name', reverse=False)
        print("\nSorted alphabetically:")
    else:
        topics = sort_topics(topics, 'article_count')
        print("\nSorted by article count (most articles first):")

    # DISPLAY TABLE
    print_topic_table(topics)

    print(f"Total topics: {len(topics)}")
    input("\nPress Enter to continue...")


def filter_by_score_menu(db: Database):
    """
    Interactive menu for filtering topics by SMB score.

    WHAT THIS DOES:
    Asks user for minimum score threshold and displays matching topics.
    """
    clear_screen()
    print_header("FILTER BY SMB RELEVANCE SCORE")

    topics = db.get_topics_with_metadata()

    if not topics:
        print("No topics found.")
        input("\nPress Enter to continue...")
        return

    # ASK FOR MINIMUM SCORE
    print("Enter minimum SMB relevance score (0-10):")
    print("  8-10: Highly relevant to SMBs")
    print("  5-7:  Moderately relevant")
    print("  0-4:  Low relevance")

    try:
        min_score = int(input("\nMinimum score: ").strip())

        if min_score < 0 or min_score > 10:
            print("Invalid score. Must be 0-10.")
            input("\nPress Enter to continue...")
            return

        # FILTER TOPICS
        filtered = filter_topics_by_score(topics, min_score)

        print(f"\nTopics with SMB score >= {min_score}:")
        print_topic_table(filtered)

        print(f"Showing {len(filtered)} of {len(topics)} topics")

    except ValueError:
        print("Invalid input. Please enter a number.")

    input("\nPress Enter to continue...")


def filter_by_article_count_menu(db: Database):
    """
    Interactive menu for filtering topics by article count.

    WHAT THIS DOES:
    Asks user for minimum article count and displays matching topics.
    """
    clear_screen()
    print_header("FILTER BY ARTICLE COUNT")

    topics = db.get_topics_with_metadata()

    if not topics:
        print("No topics found.")
        input("\nPress Enter to continue...")
        return

    # ASK FOR MINIMUM COUNT
    print("Enter minimum number of articles:")
    print("  1:   All topics")
    print("  2-3: Minimum for synthesis")
    print("  4+:  Well-covered topics")

    try:
        min_articles = int(input("\nMinimum articles: ").strip())

        if min_articles < 1:
            print("Invalid count. Must be at least 1.")
            input("\nPress Enter to continue...")
            return

        # FILTER TOPICS
        filtered = filter_topics_by_article_count(topics, min_articles)

        print(f"\nTopics with at least {min_articles} articles:")
        print_topic_table(filtered)

        print(f"Showing {len(filtered)} of {len(topics)} topics")

    except ValueError:
        print("Invalid input. Please enter a number.")

    input("\nPress Enter to continue...")


def view_topic_articles_menu(db: Database):
    """
    Interactive menu for viewing articles for a specific topic.

    WHAT THIS DOES:
    Asks user for topic ID and displays all articles for that topic.
    """
    clear_screen()
    print_header("VIEW ARTICLES FOR TOPIC")

    # SHOW AVAILABLE TOPICS FIRST
    topics = db.get_topics_with_metadata()
    if not topics:
        print("No topics found.")
        input("\nPress Enter to continue...")
        return

    print("Available topics:")
    print_topic_table(topics, show_dates=False)

    # ASK FOR TOPIC ID
    try:
        topic_id = int(input("\nEnter topic ID (or 0 to cancel): ").strip())

        if topic_id == 0:
            return

        # DISPLAY ARTICLES
        clear_screen()
        print_articles_for_topic(db, topic_id)

    except ValueError:
        print("Invalid input. Please enter a topic ID number.")

    input("\nPress Enter to continue...")


def show_statistics(db: Database):
    """
    Display comprehensive database statistics.

    WHAT THIS DOES:
    Shows overview of pipeline status: articles, topics, coverage, etc.
    """
    clear_screen()
    print_header("DATABASE STATISTICS")

    stats = db.get_stats()

    print(f"Total Articles:       {stats['total_articles']}")
    print(f"Processed Articles:   {stats['total_articles'] - stats['unprocessed_articles']}")
    print(f"Unprocessed Articles: {stats['unprocessed_articles']}")
    print(f"Total Topics:         {stats['total_topics']}")
    print(f"Total Links:          {stats['total_links']}")

    # CALCULATE AVERAGES
    if stats['total_topics'] > 0:
        avg_articles_per_topic = stats['total_links'] / stats['total_topics']
        print(f"Avg Articles/Topic:   {avg_articles_per_topic:.1f}")

    # TOP TOPICS BY ARTICLE COUNT
    topics = db.get_topics_with_metadata()
    if topics:
        sorted_topics = sort_topics(topics, 'article_count')[:5]
        print(f"\nTop 5 Topics by Article Count:")
        for i, topic in enumerate(sorted_topics, 1):
            print(f"  {i}. {topic['topic_name']} ({topic['article_count']} articles, SMB: {topic['smb_relevance_score']})")

    input("\nPress Enter to continue...")


def export_topic_list(db: Database):
    """
    Export topic list to a file for use with generate.py.

    WHAT THIS DOES:
    Creates a text file listing topic IDs that can be used with generate.py
    to batch-generate articles for multiple topics.

    OUTPUT FILE:
    topics_to_generate.txt containing one topic ID per line
    """
    clear_screen()
    print_header("EXPORT TOPIC LIST")

    # GET TOPICS
    topics = db.get_topics_with_metadata()
    if not topics:
        print("No topics found.")
        input("\nPress Enter to continue...")
        return

    # ASK FOR FILTERS
    print("Filter options:")
    print("1. All topics")
    print("2. SMB score >= 8")
    print("3. SMB score >= 8 AND article count >= 3")
    print("4. Custom filter")

    choice = input("\nChoice (1-4): ").strip()

    # APPLY FILTERS
    if choice == '2':
        topics = filter_topics_by_score(topics, 8)
    elif choice == '3':
        topics = filter_topics_by_score(topics, 8)
        topics = filter_topics_by_article_count(topics, 3)
    elif choice == '4':
        try:
            min_score = int(input("Minimum SMB score: ").strip())
            min_articles = int(input("Minimum article count: ").strip())
            topics = filter_topics_by_score(topics, min_score)
            topics = filter_topics_by_article_count(topics, min_articles)
        except ValueError:
            print("Invalid input.")
            input("\nPress Enter to continue...")
            return

    if not topics:
        print("No topics match the filter criteria.")
        input("\nPress Enter to continue...")
        return

    # SHOW TOPICS THAT WILL BE EXPORTED
    print(f"\nTopics to export ({len(topics)} topics):")
    print_topic_table(topics, show_dates=False)

    confirm = input("\nExport these topics? (y/n): ").strip().lower()

    if confirm == 'y':
        # WRITE TO FILE
        filename = 'topics_to_generate.txt'
        with open(filename, 'w') as f:
            for topic in topics:
                f.write(f"{topic['id']}\n")

        print(f"\n✓ Exported {len(topics)} topic IDs to {filename}")
        print(f"Usage: python generate.py --topics-file {filename}")
    else:
        print("Export cancelled.")

    input("\nPress Enter to continue...")


# ============================================================================
# MAIN PROGRAM
# ============================================================================

def main():
    """
    Main program loop for interactive topic browser.

    WHAT THIS DOES:
    - Initializes database connection
    - Shows main menu in a loop
    - Handles user choices
    - Exits cleanly
    """
    # INITIALIZE DATABASE
    db = Database()

    # MAIN LOOP
    while True:
        clear_screen()
        print_header("TOPIC BROWSER")

        # SHOW QUICK STATS
        stats = db.get_stats()
        print(f"Database: {stats['total_topics']} topics | {stats['total_articles']} articles | {stats['unprocessed_articles']} unprocessed")

        show_main_menu()

        choice = input("\nChoice (1-8): ").strip()

        if choice == '1':
            view_hierarchy(db)
        elif choice == '2':
            view_all_topics(db)
        elif choice == '3':
            filter_by_score_menu(db)
        elif choice == '4':
            filter_by_article_count_menu(db)
        elif choice == '5':
            view_topic_articles_menu(db)
        elif choice == '6':
            show_statistics(db)
        elif choice == '7':
            export_topic_list(db)
        elif choice == '8':
            print("\nClosing database connection...")
            db.close()
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 1-8.")
            input("\nPress Enter to continue...")


# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Entry point when script is run directly.

    USAGE:
        python view_topics.py

    PREREQUISITES:
        1. Database with topics (run compile.py first)
        2. No additional dependencies needed

    WHAT HAPPENS:
        - Launches interactive menu
        - Allows browsing and filtering topics
        - Exports topic lists for generation
    """
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        raise
