#!/usr/bin/env python3
"""
================================================================================
CONTROL CENTER - UNIFIED INTERACTIVE INTERFACE
================================================================================

PURPOSE:
Single terminal interface to control all pipeline functionality:
- Fetch articles
- Process articles (extract topics)
- View topics (hierarchy, filters, search)
- Generate articles (all modes)
- Database management
- System monitoring

USAGE:
    python control_center.py

"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from typing import List, Dict, Optional
from database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/control_center.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clear_screen():
    """Clear terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def pause():
    """Wait for user to press Enter."""
    input("\n Press Enter to continue...")


def print_header(title: str):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(title.center(80))
    print("=" * 80 + "\n")


def run_command(cmd: List[str], description: str, timeout: int = 600) -> bool:
    """
    Run a command and display output in real-time.

    Returns True if successful, False otherwise.
    """
    print(f"\n🔄 {description}...")
    print("-" * 80)

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        # Print output in real-time
        for line in process.stdout:
            print(line, end='')

        process.wait(timeout=timeout)

        if process.returncode == 0:
            print("-" * 80)
            print(f"✅ {description} completed successfully!\n")
            return True
        else:
            print("-" * 80)
            print(f"❌ {description} failed with exit code {process.returncode}\n")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ {description} timed out after {timeout} seconds\n")
        return False
    except Exception as e:
        print(f"❌ {description} failed: {e}\n")
        return False


# ============================================================================
# PHASE 1: FETCH ARTICLES
# ============================================================================

def fetch_articles_menu():
    """Fetch new articles from sources."""
    clear_screen()
    print_header("FETCH NEW ARTICLES")

    db = Database()
    stats = db.get_stats()

    print(f"Current articles in database: {stats['total_articles']}")
    print(f"Unprocessed articles: {stats['unprocessed_articles']}")

    print("\nFetch new articles from:")
    print("  - Slaw")
    print("  - McCarthy Tétrault")
    print("  - Monkhouse Law")
    print("  - Osler")
    print("  - Other configured sources")

    confirm = input("\n Proceed with fetching? (y/n): ").strip().lower()

    if confirm == 'y':
        success = run_command([sys.executable, 'fetch.py'], "Fetching articles")

        # Show updated stats
        db = Database()  # Reconnect to see new data
        new_stats = db.get_stats()
        new_articles = new_stats['total_articles'] - stats['total_articles']

        print(f"\n📊 Results:")
        print(f"  New articles fetched: {new_articles}")
        print(f"  Total articles: {new_stats['total_articles']}")
        print(f"  Ready to process: {new_stats['unprocessed_articles']}")

        db.close()

    pause()


# ============================================================================
# PHASE 2: PROCESS ARTICLES (COMPILE)
# ============================================================================

def process_articles_menu():
    """Extract topics from unprocessed articles."""
    clear_screen()
    print_header("PROCESS ARTICLES (EXTRACT TOPICS)")

    db = Database()
    stats = db.get_stats()

    print(f"Unprocessed articles: {stats['unprocessed_articles']}")
    print(f"Current topics: {stats['total_topics']}")

    if stats['unprocessed_articles'] == 0:
        print("\n✅ No articles to process. All articles have been processed!")
        db.close()
        pause()
        return

    # Estimate cost
    estimated_cost = stats['unprocessed_articles'] * 0.001
    print(f"\nEstimated cost: ${estimated_cost:.2f} (Gemini 2.5 Flash)")
    print(f"Estimated time: ~{stats['unprocessed_articles'] * 3} seconds")

    print("\nThis will:")
    print("  1. Extract parent topics (Employment Law, Contract Law, etc.)")
    print("  2. Extract subtopics (Wrongful Dismissal, Data Breach Response, etc.)")
    print("  3. Create hierarchical relationships")
    print("  4. Link articles to subtopics")

    confirm = input("\n Proceed with processing? (y/n): ").strip().lower()

    if confirm == 'y':
        success = run_command(
            [sys.executable, 'compile.py'],
            "Processing articles",
            timeout=1800
        )

        # Show updated stats
        db = Database()  # Reconnect
        new_stats = db.get_stats()

        print(f"\n📊 Results:")
        print(f"  Articles processed: {stats['unprocessed_articles'] - new_stats['unprocessed_articles']}")
        print(f"  Total topics: {new_stats['total_topics']}")
        print(f"  Remaining unprocessed: {new_stats['unprocessed_articles']}")

        db.close()

    pause()


# ============================================================================
# PHASE 3: VIEW TOPICS
# ============================================================================

def view_topics_hierarchy(db: Database):
    """Display topics in hierarchical tree view."""
    clear_screen()
    print_header("TOPIC HIERARCHY")

    parent_topics = db.get_parent_topics()

    if not parent_topics:
        print("No parent topics found. Run 'Process Articles' first.")
        pause()
        return

    print("TOPICS BY CATEGORY")
    print("=" * 80 + "\n")

    for parent in parent_topics:
        parent_name = parent['topic_name']
        parent_score = parent.get('smb_relevance_score', 10)
        parent_id = parent['id']

        subtopics = db.get_subtopics_for_parent(parent_id)
        total_articles = sum(st.get('article_count', 0) for st in subtopics)

        print(f"{parent_name} ({parent_score}/10 SMB) - {total_articles} articles [ID: {parent_id}]")

        if subtopics:
            for i, subtopic in enumerate(subtopics):
                is_last = (i == len(subtopics) - 1)
                tree_char = "└──" if is_last else "├──"

                name = subtopic['topic_name']
                score = subtopic.get('smb_relevance_score', 'N/A')
                count = subtopic.get('article_count', 0)
                st_id = subtopic['id']

                print(f"{tree_char} {name} ({score}/10) - {count} articles [ID: {st_id}]")

        print()

    print(f"Total: {len(parent_topics)} parent categories")
    pause()


def view_topics_menu():
    """View topics with various display options."""
    db = Database()

    while True:
        clear_screen()
        print_header("VIEW TOPICS")

        stats = db.get_stats()
        print(f"Database: {stats['total_topics']} topics | {stats['total_articles']} articles\n")

        print("1. View hierarchy (tree view)")
        print("2. View all topics (table)")
        print("3. Search topics by name")
        print("4. Filter by SMB score")
        print("5. Filter by article count")
        print("6. View articles for specific topic")
        print("7. Show database statistics")
        print("8. Back to main menu")

        choice = input("\n Choice (1-8): ").strip()

        if choice == '1':
            view_topics_hierarchy(db)
        elif choice == '2':
            # Launch full view_topics.py for advanced features
            run_command([sys.executable, 'view_topics.py'], "Launching topic viewer")
            pause()
        elif choice == '3':
            search_topics(db)
        elif choice == '4':
            filter_by_score(db)
        elif choice == '5':
            filter_by_count(db)
        elif choice == '6':
            view_topic_articles(db)
        elif choice == '7':
            show_detailed_stats(db)
        elif choice == '8':
            db.close()
            break
        else:
            print("Invalid choice. Please enter 1-8.")
            pause()


def search_topics(db: Database):
    """Search topics by name."""
    clear_screen()
    print_header("SEARCH TOPICS")

    query = input(" Enter search term: ").strip()

    if not query:
        return

    all_topics = db.get_all_topics()
    matches = [t for t in all_topics if query.lower() in t['topic_name'].lower()]

    if not matches:
        print(f"\nNo topics found matching '{query}'")
    else:
        print(f"\nFound {len(matches)} matching topics:\n")
        for topic in matches:
            print(f"[ID: {topic['id']}] {topic['topic_name']}")
            print(f"    SMB Score: {topic.get('smb_relevance_score', 'N/A')}/10 | Articles: {topic.get('article_count', 0)}")
            print()

    pause()


def filter_by_score(db: Database):
    """Filter topics by minimum SMB score."""
    clear_screen()
    print_header("FILTER BY SMB SCORE")

    try:
        min_score = int(input(" Minimum SMB score (0-10): ").strip())

        if min_score < 0 or min_score > 10:
            print("Invalid score. Must be 0-10.")
            pause()
            return

        all_topics = db.get_topics_with_metadata()
        filtered = [t for t in all_topics if t.get('smb_relevance_score', 0) >= min_score]

        print(f"\nTopics with SMB score >= {min_score}: {len(filtered)}\n")

        for topic in filtered[:20]:  # Show first 20
            print(f"[ID: {topic['id']}] {topic['topic_name']}")
            print(f"    Score: {topic.get('smb_relevance_score', 'N/A')}/10 | Articles: {topic.get('article_count', 0)}")

        if len(filtered) > 20:
            print(f"\n... and {len(filtered) - 20} more")

    except ValueError:
        print("Invalid input.")

    pause()


def filter_by_count(db: Database):
    """Filter topics by minimum article count."""
    clear_screen()
    print_header("FILTER BY ARTICLE COUNT")

    try:
        min_count = int(input(" Minimum article count: ").strip())

        all_topics = db.get_topics_with_metadata()
        filtered = [t for t in all_topics if t.get('article_count', 0) >= min_count]

        # Sort by article count descending
        filtered.sort(key=lambda t: t.get('article_count', 0), reverse=True)

        print(f"\nTopics with >= {min_count} articles: {len(filtered)}\n")

        for topic in filtered[:20]:
            print(f"[ID: {topic['id']}] {topic['topic_name']}")
            print(f"    Articles: {topic.get('article_count', 0)} | Score: {topic.get('smb_relevance_score', 'N/A')}/10")

        if len(filtered) > 20:
            print(f"\n... and {len(filtered) - 20} more")

    except ValueError:
        print("Invalid input.")

    pause()


def view_topic_articles(db: Database):
    """View all articles for a specific topic."""
    clear_screen()
    print_header("VIEW TOPIC ARTICLES")

    try:
        topic_id = int(input(" Enter topic ID: ").strip())

        topic = db.get_topic_by_id(topic_id)
        if not topic:
            print(f"Topic ID {topic_id} not found.")
            pause()
            return

        articles = db.get_articles_for_topic(topic_id)

        print(f"\nTopic: {topic['topic_name']}")
        print(f"Articles: {len(articles)}\n")
        print("=" * 80)

        for i, article in enumerate(articles, 1):
            print(f"\n{i}. {article['title']}")
            print(f"   Source: {article['source']} | Date: {article.get('published_date', 'Unknown')[:10]}")
            print(f"   URL: {article['url']}")

    except ValueError:
        print("Invalid topic ID.")

    pause()


def show_detailed_stats(db: Database):
    """Show comprehensive database statistics."""
    clear_screen()
    print_header("DATABASE STATISTICS")

    stats = db.get_stats()

    print(f"📊 ARTICLES")
    print(f"  Total:       {stats['total_articles']}")
    print(f"  Processed:   {stats['total_articles'] - stats['unprocessed_articles']}")
    print(f"  Unprocessed: {stats['unprocessed_articles']}")

    print(f"\n📁 TOPICS")
    print(f"  Total topics:  {stats['total_topics']}")
    print(f"  Total links:   {stats['total_links']}")

    parent_count = len(db.get_parent_topics())
    print(f"  Parent topics: {parent_count}")
    print(f"  Subtopics:     {stats['total_topics'] - parent_count}")

    if stats['total_topics'] > 0:
        avg = stats['total_links'] / stats['total_topics']
        print(f"  Avg articles/topic: {avg:.1f}")

    print(f"\n📝 GENERATED ARTICLES")
    output_dir = 'output/generated_articles'
    if os.path.exists(output_dir):
        count = len([f for f in os.listdir(output_dir) if f.endswith('.md')])
        print(f"  Generated articles: {count}")
    else:
        print(f"  Generated articles: 0")

    print(f"\n🏆 TOP 5 TOPICS BY COVERAGE")
    topics = db.get_topics_with_metadata()
    if topics:
        sorted_topics = sorted(topics, key=lambda t: t.get('article_count', 0), reverse=True)[:5]
        for i, topic in enumerate(sorted_topics, 1):
            print(f"  {i}. {topic['topic_name']}")
            print(f"     {topic['article_count']} articles | SMB Score: {topic.get('smb_relevance_score', 'N/A')}/10")

    pause()


# ============================================================================
# PHASE 4: GENERATE ARTICLES
# ============================================================================

def generate_articles_menu():
    """Generate articles with various options."""
    db = Database()

    while True:
        clear_screen()
        print_header("GENERATE ARTICLES")

        print("1. Generate by subtopic (focused)")
        print("2. Generate by parent topic (comprehensive)")
        print("3. Combine multiple subtopics")
        print("4. Auto-generate top topics")
        print("5. Browse and select from hierarchy")
        print("6. Back to main menu")

        choice = input("\n Choice (1-6): ").strip()

        if choice == '1':
            generate_by_subtopic(db)
        elif choice == '2':
            generate_by_parent(db)
        elif choice == '3':
            generate_combined(db)
        elif choice == '4':
            auto_generate(db)
        elif choice == '5':
            browse_and_generate(db)
        elif choice == '6':
            db.close()
            break
        else:
            print("Invalid choice.")
            pause()


def generate_by_subtopic(db: Database):
    """Generate article for single subtopic."""
    clear_screen()
    print_header("GENERATE BY SUBTOPIC")

    try:
        topic_id = int(input(" Enter subtopic ID: ").strip())

        topic = db.get_topic_by_id(topic_id)
        if not topic:
            print(f"Topic ID {topic_id} not found.")
            pause()
            return

        print(f"\nTopic: {topic['topic_name']}")
        print(f"SMB Score: {topic.get('smb_relevance_score', 'N/A')}/10")

        articles = db.get_articles_for_topic(topic_id)
        print(f"Source articles: {len(articles)}")

        # Model selection
        model = input("\n Model (sonnet/haiku) [sonnet]: ").strip().lower() or 'sonnet'

        confirm = input("\n Proceed with generation? (y/n): ").strip().lower()

        if confirm == 'y':
            run_command(
                [sys.executable, 'generate.py', '--topic', str(topic_id), '--model', model],
                "Generating article",
                timeout=600
            )

    except ValueError:
        print("Invalid input.")

    pause()


def generate_by_parent(db: Database):
    """Generate comprehensive article from all subtopics under parent."""
    clear_screen()
    print_header("GENERATE BY PARENT TOPIC")

    # Show parent topics
    parents = db.get_parent_topics()

    if not parents:
        print("No parent topics found.")
        pause()
        return

    print("Available parent topics:\n")
    for parent in parents:
        subtopics = db.get_subtopics_for_parent(parent['id'])
        total = sum(st.get('article_count', 0) for st in subtopics)
        print(f"[ID: {parent['id']}] {parent['topic_name']}")
        print(f"    {len(subtopics)} subtopics | {total} total articles\n")

    try:
        parent_id = int(input(" Enter parent topic ID: ").strip())

        parent = db.get_topic_by_id(parent_id)
        if not parent or parent.get('is_parent', 0) != 1:
            print("Invalid parent topic ID.")
            pause()
            return

        subtopics = db.get_subtopics_for_parent(parent_id)
        print(f"\nThis will combine {len(subtopics)} subtopics:")
        for st in subtopics:
            print(f"  - {st['topic_name']} ({st.get('article_count', 0)} articles)")

        model = input("\n Model (sonnet/haiku) [sonnet]: ").strip().lower() or 'sonnet'

        confirm = input("\n Proceed? (y/n): ").strip().lower()

        if confirm == 'y':
            run_command(
                [sys.executable, 'generate.py', '--parent', str(parent_id), '--model', model],
                "Generating comprehensive article",
                timeout=600
            )

    except ValueError:
        print("Invalid input.")

    pause()


def generate_combined(db: Database):
    """Combine specific subtopics."""
    clear_screen()
    print_header("COMBINE SUBTOPICS")

    print("Enter subtopic IDs separated by spaces (e.g., 2 5 8)")
    ids_input = input(" Subtopic IDs: ").strip()

    try:
        topic_ids = [int(x) for x in ids_input.split()]

        if not topic_ids:
            print("No IDs provided.")
            pause()
            return

        print(f"\nCombining {len(topic_ids)} subtopics:")
        total_articles = 0
        for tid in topic_ids:
            topic = db.get_topic_by_id(tid)
            if topic:
                articles = db.get_articles_for_topic(tid)
                print(f"  - {topic['topic_name']} ({len(articles)} articles)")
                total_articles += len(articles)

        print(f"\nTotal source articles: ~{total_articles} (will deduplicate)")

        model = input("\n Model (sonnet/haiku) [sonnet]: ").strip().lower() or 'sonnet'

        confirm = input("\n Proceed? (y/n): ").strip().lower()

        if confirm == 'y':
            cmd = [sys.executable, 'generate.py', '--subtopics'] + [str(tid) for tid in topic_ids]
            cmd.extend(['--model', model])
            run_command(cmd, "Generating combined article", timeout=600)

    except ValueError:
        print("Invalid input.")

    pause()


def auto_generate(db: Database):
    """Auto-generate articles for top topics."""
    clear_screen()
    print_header("AUTO-GENERATE TOP TOPICS")

    print("This will automatically select and generate articles for high-value topics.\n")

    try:
        min_score = int(input(" Minimum SMB score [8]: ").strip() or "8")
        min_articles = int(input(" Minimum article count [3]: ").strip() or "3")
        max_topics = int(input(" Maximum topics to generate [5]: ").strip() or "5")
        model = input(" Model (sonnet/haiku) [sonnet]: ").strip().lower() or 'sonnet'

        # Filter topics
        all_topics = db.get_topics_with_metadata()
        filtered = [
            t for t in all_topics
            if t.get('smb_relevance_score', 0) >= min_score
            and t.get('article_count', 0) >= min_articles
        ]

        # Sort by article count
        filtered.sort(key=lambda t: t.get('article_count', 0), reverse=True)
        selected = filtered[:max_topics]

        print(f"\nSelected {len(selected)} topics:")
        for topic in selected:
            print(f"  - {topic['topic_name']} (Score: {topic.get('smb_relevance_score')}/10, Articles: {topic.get('article_count')})")

        if not selected:
            print("\nNo topics match criteria.")
            pause()
            return

        # Estimate cost
        if model == 'sonnet':
            cost_per = 0.12
        else:
            cost_per = 0.01

        print(f"\nEstimated cost: ${len(selected) * cost_per:.2f}")

        confirm = input("\n Proceed? (y/n): ").strip().lower()

        if confirm == 'y':
            topic_ids = [str(t['id']) for t in selected]
            cmd = [sys.executable, 'generate.py', '--topics'] + topic_ids + ['--model', model]
            run_command(cmd, f"Generating {len(selected)} articles", timeout=1800)

    except ValueError:
        print("Invalid input.")

    pause()


def browse_and_generate(db: Database):
    """Browse hierarchy and select topic to generate."""
    view_topics_hierarchy(db)

    try:
        topic_id = int(input("\n Enter topic ID to generate (0 to cancel): ").strip())

        if topic_id == 0:
            return

        topic = db.get_topic_by_id(topic_id)
        if not topic:
            print("Topic not found.")
            pause()
            return

        model = input(" Model (sonnet/haiku) [sonnet]: ").strip().lower() or 'sonnet'

        run_command(
            [sys.executable, 'generate.py', '--topic', str(topic_id), '--model', model],
            "Generating article",
            timeout=600
        )

    except ValueError:
        print("Invalid input.")

    pause()


# ============================================================================
# PHASE 5: DATABASE MANAGEMENT
# ============================================================================

def database_menu():
    """Database management operations."""
    db = Database()

    while True:
        clear_screen()
        print_header("DATABASE MANAGEMENT")

        print("1. Show statistics")
        print("2. Reset topics (keep articles)")
        print("3. Complete database reset")
        print("4. Export topics to file")
        print("5. View SQL database directly")
        print("6. Back to main menu")

        choice = input("\n Choice (1-6): ").strip()

        if choice == '1':
            show_detailed_stats(db)
        elif choice == '2':
            reset_topics()
        elif choice == '3':
            complete_reset()
        elif choice == '4':
            export_topics(db)
        elif choice == '5':
            view_database_sql()
        elif choice == '6':
            db.close()
            break
        else:
            print("Invalid choice.")
            pause()


def reset_topics():
    """Reset topics and mark articles as unprocessed."""
    clear_screen()
    print_header("RESET TOPICS")

    print("⚠️  WARNING: This will:")
    print("  - Delete all topics")
    print("  - Delete all article-topic relationships")
    print("  - Mark all articles as unprocessed")
    print("  - Keep all articles (you can reprocess them)")

    confirm = input("\n Are you sure? Type 'RESET' to confirm: ").strip()

    if confirm == 'RESET':
        import sqlite3
        conn = sqlite3.connect('data/pipeline.db')
        conn.execute("DELETE FROM article_topics")
        conn.execute("DELETE FROM topics")
        conn.execute("UPDATE articles SET processed = 0")
        conn.commit()
        conn.close()

        print("\n✅ Topics reset successfully!")
        print("   Run 'Process Articles' to re-extract topics with hierarchy.")
    else:
        print("\n❌ Reset cancelled.")

    pause()


def complete_reset():
    """Complete database reset."""
    clear_screen()
    print_header("COMPLETE DATABASE RESET")

    print("⚠️  WARNING: This will DELETE EVERYTHING:")
    print("  - All articles")
    print("  - All topics")
    print("  - All relationships")
    print("\n  You'll need to fetch and process articles again.")

    confirm = input("\n Are you ABSOLUTELY sure? Type 'DELETE EVERYTHING' to confirm: ").strip()

    if confirm == 'DELETE EVERYTHING':
        import sqlite3
        conn = sqlite3.connect('data/pipeline.db')
        conn.execute("DELETE FROM article_topics")
        conn.execute("DELETE FROM topics")
        conn.execute("DELETE FROM articles")
        conn.commit()
        conn.close()

        print("\n✅ Database completely reset!")
        print("   Run 'Fetch Articles' to start fresh.")
    else:
        print("\n❌ Reset cancelled.")

    pause()


def export_topics(db: Database):
    """Export topic IDs to file."""
    clear_screen()
    print_header("EXPORT TOPICS")

    print("Export options:")
    print("1. All topics")
    print("2. High-value topics (SMB >= 8, Articles >= 3)")
    print("3. Parent topics only")
    print("4. Custom filter")

    choice = input("\n Choice (1-4): ").strip()

    all_topics = db.get_all_topics()

    if choice == '1':
        topics = all_topics
    elif choice == '2':
        topics = [t for t in all_topics
                 if t.get('smb_relevance_score', 0) >= 8
                 and t.get('article_count', 0) >= 3]
    elif choice == '3':
        topics = db.get_parent_topics()
    elif choice == '4':
        try:
            min_score = int(input(" Minimum SMB score: ").strip())
            min_articles = int(input(" Minimum articles: ").strip())
            topics = [t for t in all_topics
                     if t.get('smb_relevance_score', 0) >= min_score
                     and t.get('article_count', 0) >= min_articles]
        except ValueError:
            print("Invalid input.")
            pause()
            return
    else:
        print("Invalid choice.")
        pause()
        return

    if not topics:
        print("\nNo topics match criteria.")
        pause()
        return

    filename = 'topics_to_generate.txt'
    with open(filename, 'w') as f:
        for topic in topics:
            f.write(f"{topic['id']}\n")

    print(f"\n✅ Exported {len(topics)} topic IDs to {filename}")
    print(f"   Use: python generate.py --topics-file {filename}")

    pause()


def view_database_sql():
    """View database using sqlite3 CLI."""
    clear_screen()
    print_header("SQL DATABASE VIEWER")

    print("Launching sqlite3 CLI...")
    print("Useful commands:")
    print("  .tables                    - List all tables")
    print("  .schema topics             - Show topics table schema")
    print("  SELECT * FROM topics;      - View all topics")
    print("  .quit                      - Exit sqlite3\n")

    pause()

    subprocess.run(['sqlite3', 'data/pipeline.db'])


# ============================================================================
# MAIN MENU
# ============================================================================

def main_menu():
    """Main control center menu."""
    while True:
        clear_screen()
        print_header("LEGAL NEWS PIPELINE - CONTROL CENTER")

        # Quick stats
        try:
            db = Database()
            stats = db.get_stats()
            print(f"📊 Quick Stats: {stats['total_articles']} articles | {stats['total_topics']} topics | {stats['unprocessed_articles']} unprocessed")
            db.close()
        except:
            print("📊 Database not initialized")

        print("\n" + "-" * 80)
        print("MAIN MENU")
        print("-" * 80)
        print("1. 📥 Fetch new articles")
        print("2. ⚙️  Process articles (extract topics)")
        print("3. 📁 View topics")
        print("4. ✍️  Generate articles")
        print("5. 🗄️  Database management")
        print("6. 📖 View documentation")
        print("7. 🚪 Exit")
        print("-" * 80)

        choice = input("\n Choice (1-7): ").strip()

        if choice == '1':
            fetch_articles_menu()
        elif choice == '2':
            process_articles_menu()
        elif choice == '3':
            view_topics_menu()
        elif choice == '4':
            generate_articles_menu()
        elif choice == '5':
            database_menu()
        elif choice == '6':
            show_documentation()
        elif choice == '7':
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid choice. Please enter 1-7.")
            pause()


def show_documentation():
    """Show documentation and help."""
    clear_screen()
    print_header("DOCUMENTATION")

    print("📚 Available Documentation:\n")
    print("1. COMMANDS_REFERENCE.md - Complete command reference")
    print("2. README.md - Project overview")

    docs = [
        ('COMMANDS_REFERENCE.md', 'Complete command reference with examples'),
        ('README.md', 'Project overview and setup instructions'),
    ]

    print("\nDocumentation files:")
    for i, (filename, desc) in enumerate(docs, 1):
        if os.path.exists(filename):
            print(f"  {i}. {filename} - {desc}")
        else:
            print(f"  {i}. {filename} - NOT FOUND")

    print("\nYou can also run individual scripts:")
    print("  python fetch.py        - Fetch articles")
    print("  python compile.py      - Extract topics")
    print("  python view_topics.py  - Interactive topic browser")
    print("  python generate.py --help  - Generation options")

    pause()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    """
    Entry point for control center.

    USAGE:
        python control_center.py
    """

    # Ensure directories exist
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('output/generated_articles', exist_ok=True)

    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")
        print("Check logs/control_center.log for details")
