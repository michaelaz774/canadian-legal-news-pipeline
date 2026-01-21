# Continuation Prompt for Canadian Legal News Pipeline

## Project Overview

This is a **Canadian Legal News Pipeline** that automatically:
1. Fetches legal articles from Canadian sources (Slaw, McCarthy Tétrault, Monkhouse Law, etc.)
2. Extracts hierarchical topics using AI (Gemini 2.5 Flash)
3. Generates comprehensive SMB-focused articles by synthesizing multiple sources (Claude)

**Target audience:** Small and medium-sized business owners in Canada who need plain-language legal guidance.

**Current status:** Fully functional with 3-level hierarchical topic system and generation tracking.

---

## Architecture Summary

### Pipeline Phases

**Phase 1: Fetch** (`fetch.py`)
- Scrapes legal news from RSS feeds and web sources
- Stores articles in SQLite database with deduplication
- ~60 articles currently in database

**Phase 2: Compile** (`compile.py`)
- Uses Gemini 2.5 Flash AI to extract topics from articles
- Implements **3-level hierarchy**:
  - **Parent Topic**: Broad category (Employment Law, Contract Law, etc.)
  - **Subtopic**: Standard grouping (Wrongful Dismissal, Data Breach Response, etc.)
  - **Article Tag**: Specific aspect per article ("Wrongful dismissal during pregnancy leave")
- Creates hierarchical relationships in database
- Cost: ~$0.001 per article

**Phase 3: Generate** (`generate.py`)
- Uses Claude (Sonnet 3.5 or Haiku) to synthesize articles
- Combines multiple source articles on same subtopic
- Generates comprehensive SMB-focused articles
- Tracks generations to avoid duplicates
- Cost: $0.12 per article (Sonnet) or $0.01 (Haiku)

**User Interfaces:**
- `control_center.py` - Unified interactive terminal interface for all operations
- `view_topics.py` - Interactive topic browser with hierarchy view
- `main.py` - Automated pipeline for scheduled runs

---

## Database Schema

**Location:** `data/pipeline.db` (SQLite)

### Tables

#### 1. `articles`
Stores fetched articles from legal news sources.

```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    source TEXT NOT NULL,
    published_date TEXT,
    fetched_date TEXT NOT NULL,
    processed INTEGER DEFAULT 0
);
```

**Key fields:**
- `processed`: 0 = unprocessed, 1 = topics extracted
- `url`: UNIQUE constraint prevents duplicates

#### 2. `topics`
Stores hierarchical topics (both parents and subtopics).

```sql
CREATE TABLE topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_name TEXT UNIQUE NOT NULL,
    category TEXT,
    key_entity TEXT,
    smb_relevance_score INTEGER,
    parent_topic_id INTEGER,           -- NEW: Links to parent topic
    is_parent INTEGER DEFAULT 0,       -- NEW: 1=parent, 0=subtopic
    created_date TEXT NOT NULL,
    FOREIGN KEY (parent_topic_id) REFERENCES topics(id)
);
```

**Key fields:**
- `is_parent`: 1 for parent topics (Employment Law), 0 for subtopics (Wrongful Dismissal)
- `parent_topic_id`: Links subtopic to parent (NULL for parents)
- `smb_relevance_score`: 0-10 rating for SMB relevance

#### 3. `article_topics`
Links articles to subtopics (many-to-many).

```sql
CREATE TABLE article_topics (
    article_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    article_tag TEXT,                  -- NEW: Specific aspect discussed
    created_date TEXT NOT NULL,
    PRIMARY KEY (article_id, topic_id),
    FOREIGN KEY (article_id) REFERENCES articles(id),
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

**Key fields:**
- `article_tag`: Level 3 of hierarchy - describes unique aspect of this article
- PRIMARY KEY prevents duplicate links

#### 4. `generated_articles`
Tracks which subtopics have been generated (prevents duplicates).

```sql
CREATE TABLE generated_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,         -- Subtopic that was generated
    generated_date TEXT NOT NULL,
    output_file TEXT NOT NULL,         -- Path to .md file
    model_used TEXT NOT NULL,          -- "sonnet" or "haiku"
    source_article_count INTEGER NOT NULL,
    word_count INTEGER,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

---

## File Structure

### Core Pipeline Files

**Fetching:**
- `fetch.py` - Scrapes articles from sources
- `config.py` - Source configurations (RSS feeds, selectors)

**Processing:**
- `compile.py` - Topic extraction with Gemini AI
- `database.py` - All database operations (CRUD for articles, topics, links)

**Generation:**
- `generate.py` - Article synthesis with Claude AI

**User Interfaces:**
- `control_center.py` - ⭐ Main interactive interface (USE THIS)
- `view_topics.py` - Topic browser with hierarchy view
- `main.py` - Automated pipeline runner

**Migrations:**
- `migration_add_hierarchy.py` - Adds parent_topic_id, is_parent columns
- `migration_add_article_tags_and_tracking.py` - Adds article_tag, generated_articles table
- `setup_3_level_system.sh` - Automated setup script

**Documentation:**
- `COMMANDS_REFERENCE.md` - Complete command reference
- `3_LEVEL_HIERARCHY_GUIDE.md` - Explains 3-level system
- `README.md` - Project overview
- `CONTINUATION_PROMPT.md` - This file

**Configuration:**
- `.env` - API keys (GEMINI_API_KEY, ANTHROPIC_API_KEY)
- `requirements.txt` - Python dependencies

**Data:**
- `data/pipeline.db` - SQLite database
- `output/generated_articles/` - Generated markdown files
- `logs/` - Log files for each module

---

## Current Implementation Details

### 3-Level Hierarchy System

**Level 1: Parent Topics** (11 total)
Broad categories for organization:
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
- Criminal Law

**Level 2: Subtopics** (Standard categories for grouping)

Employment Law subtopics:
- Wrongful Dismissal
- Workplace Harassment & Discrimination
- Employment Contracts & Termination
- Employee Classification & Rights
- Workplace Safety & Accommodation
- Severance & Termination Pay
- Employment Standards & Leaves

Privacy & Data Protection subtopics:
- Data Breach Response
- PIPEDA Compliance
- AI & Data Governance
- Government Data Access

*(See compile.py lines 340-387 for complete list)*

**Level 3: Article Tags**
Unique aspect of each article (5-8 words):
- "Wrongful dismissal during pregnancy leave"
- "Constructive dismissal hostile work environment"
- "PIPEDA breach notification requirements"

### Generation Tracking System

**How it works:**
1. When article is generated, entry added to `generated_articles` table
2. Database methods check if topic already generated before suggesting
3. UI shows ✅ for generated topics, ⚠️ for ungenerated
4. Auto-generate automatically skips already-generated topics

**Key database methods:**
- `db.track_generation(topic_id, output_file, model_used, ...)` - Records generation
- `db.is_topic_generated(topic_id)` - Check if generated
- `db.get_ungenerated_subtopics(min_score, min_articles)` - Find what needs generation
- `db.get_generation_info(topic_id)` - Get generation details

---

## How Each Component Works

### compile.py - Topic Extraction

**Process:**
1. Get unprocessed articles from database (`processed=0`)
2. For each article:
   - Send full content to Gemini 2.5 Flash
   - Receive structured JSON with parent_topic, subtopic, article_tag, score, reasoning
   - Find or create parent topic (is_parent=1)
   - Find or create subtopic under parent (is_parent=0, parent_topic_id set)
   - Link article to subtopic with article_tag
   - Mark article as processed
3. Log success/failure for each article

**Key features:**
- Uses Pydantic schemas for validation
- Retry logic with exponential backoff for rate limits
- Idempotent (can run multiple times safely)
- Provides standard subtopic names to AI for consistency

**Prompt engineering:**
- Lists standard subtopics for each parent to encourage grouping
- Asks for 3 pieces: parent, subtopic, and article tag
- Emphasizes SMB relevance scoring

### generate.py - Article Synthesis

**Generation modes:**
1. **By subtopic** (`--topic ID`) - Generate from one subtopic's articles
2. **By parent** (`--parent ID`) - Combine all subtopics under parent
3. **Combine subtopics** (`--subtopics ID1 ID2 ID3`) - Merge specific subtopics
4. **Multiple separate** (`--topics ID1 ID2 ID3`) - Generate each separately
5. **From file** (`--topics-file file.txt`) - Batch generation

**Process:**
1. Fetch topic info and articles
2. If parent topic: get all subtopics and their articles
3. Deduplicate articles (if article tagged with multiple subtopics)
4. Send to Claude with synthesis prompt
5. Save as markdown with metadata header
6. Track generation in database

**Synthesis prompt:**
- Target audience: Canadian SMB owners with no legal background
- Structure: Opening, Key Insights, Practical Implications, Action Items, Resources
- Tone: Professional but conversational
- Length: 1500-2000 words
- Citations: Informal references to source articles

### control_center.py - Unified Interface

**Main menu:**
1. Fetch new articles
2. Process articles (extract topics)
3. View topics (hierarchy, search, filters)
4. Generate articles (all modes)
5. Database management (reset, stats, export)
6. View documentation
7. Exit

**Features:**
- Real-time output streaming
- Input validation
- Cost estimates before operations
- Status indicators (✅ generated, ⚠️ ungenerated)
- Integrated help

---

## Common Tasks

### Task 1: Fetch and Process New Articles

**Via Control Center:**
```bash
python control_center.py
# 1. Choose option 1 (Fetch)
# 2. Choose option 2 (Process)
# 3. Choose option 3 → 1 (View hierarchy)
```

**Via command line:**
```bash
python fetch.py
python compile.py
python view_topics.py
```

### Task 2: Generate Article for Subtopic

**Via Control Center:**
```bash
python control_center.py
# Choose: 4 (Generate) → 1 (By subtopic)
# Enter subtopic ID
# Select model (sonnet or haiku)
```

**Via command line:**
```bash
python generate.py --topic 42 --model sonnet
```

### Task 3: View What Needs Generation

**Via Control Center:**
```bash
python control_center.py
# Choose: 3 (View) → 4 (Filter by article count)
# Enter minimum: 3
# Look for topics marked ⚠️ Not generated
```

**Via database query:**
```bash
sqlite3 data/pipeline.db
SELECT t.id, t.topic_name, COUNT(at.article_id) as articles
FROM topics t
LEFT JOIN article_topics at ON t.id = at.topic_id
WHERE t.is_parent = 0
  AND t.id NOT IN (SELECT topic_id FROM generated_articles)
GROUP BY t.id
HAVING COUNT(at.article_id) >= 3
ORDER BY articles DESC;
```

### Task 4: Reset Topics and Reprocess

**Via Control Center:**
```bash
python control_center.py
# Choose: 5 (Database) → 2 (Reset topics)
# Confirm with "RESET"
# Then: 2 (Process articles)
```

**Via command line:**
```bash
sqlite3 data/pipeline.db "DELETE FROM article_topics; DELETE FROM topics; UPDATE articles SET processed = 0;"
python compile.py
```

### Task 5: Export Topics for Batch Generation

**Via Control Center:**
```bash
python control_center.py
# Choose: 5 (Database) → 4 (Export)
# Select filter option
# Creates: topics_to_generate.txt
```

**Then batch generate:**
```bash
python generate.py --topics-file topics_to_generate.txt --model haiku
```

---

## Environment Setup

### Required Environment Variables

Create `.env` file:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

**Get API keys:**
- Gemini: https://aistudio.google.com/app/apikey (free tier available)
- Anthropic: https://console.anthropic.com/ (requires payment)

### Python Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies:
- `google-genai` - Gemini AI SDK (NEW unified SDK)
- `anthropic` - Claude AI SDK
- `pydantic` - Schema validation
- `tenacity` - Retry logic
- `tqdm` - Progress bars
- `beautifulsoup4` - HTML parsing
- `feedparser` - RSS parsing

---

## Troubleshooting

### Problem: Topics are too fragmented (each subtopic has 1 article)

**Cause:** AI created unique subtopics instead of using standard ones.

**Solution:**
1. Check compile.py lines 340-387 - ensure standard subtopics are listed
2. Reset and reprocess:
   ```bash
   python control_center.py → 5 → 2 (Reset topics)
   python control_center.py → 2 (Process articles)
   ```

### Problem: "Column article_tag doesn't exist"

**Cause:** Need to run article tags migration.

**Solution:**
```bash
python migration_add_article_tags_and_tracking.py
```

### Problem: "Table generated_articles doesn't exist"

**Cause:** Need to run generation tracking migration.

**Solution:**
```bash
python migration_add_article_tags_and_tracking.py
```

### Problem: Gemini rate limit errors

**Cause:** Free tier limits: 10 requests/minute, 1000 requests/day.

**Solution:**
- Wait and run again tomorrow
- Upgrade to paid tier
- Processing is idempotent - progress is saved

### Problem: Claude API errors during generation

**Cause:** Invalid API key or quota exceeded.

**Solution:**
1. Check `.env` has valid `ANTHROPIC_API_KEY`
2. Check account has credits: https://console.anthropic.com/
3. Try cheaper model: `--model haiku`

### Problem: Database locked errors

**Cause:** Multiple processes accessing database simultaneously.

**Solution:**
- Close all instances of scripts
- Restart control_center.py
- Check for background processes: `ps aux | grep python`

---

## Code Patterns and Conventions

### Database Operations

**Always use Database class methods, never raw SQL:**
```python
# GOOD
db = Database()
topic_id = db.find_or_create_topic(
    topic_name="Employment Law",
    is_parent=True
)

# BAD - Don't write raw SQL
cursor.execute("INSERT INTO topics ...")
```

### Error Handling

**Continue processing on errors, log details:**
```python
for article in articles:
    try:
        # Process article
        process_article(article)
    except Exception as e:
        logger.error(f"Failed to process {article['id']}: {e}")
        continue  # Don't stop entire batch
```

### Logging

**Use structured logging:**
```python
logger.info(f"✓ Extracted topics: {topic_names}")
logger.error(f"✗ Failed to process article {article_id}")
logger.debug(f"Linked article {article_id} to topic {topic_id}")
```

### Cost Tracking

**Always log token usage and costs:**
```python
logger.info(f"  Input tokens: {input_tokens:,}")
logger.info(f"  Output tokens: {output_tokens:,}")
logger.info(f"  Estimated cost: ${total_cost:.4f}")
```

---

## Next Steps and Improvements

### Immediate Enhancements

1. **Add article tags to UI display**
   - Show tags when viewing articles for a topic
   - Allow filtering by tag

2. **Enhanced generation tracking UI**
   - Show generation date in hierarchy view
   - Allow regeneration with confirmation
   - Show generation history for each topic

3. **Smart auto-generate**
   - Prioritize high SMB score + high article count
   - Skip generated topics automatically
   - Estimate total cost before batch

4. **Article quality scoring**
   - Track user feedback on generated articles
   - Use scores to refine prompts
   - Filter topics by generation quality

### Medium-term Improvements

1. **Scheduled automation**
   - Cron job to run fetch + compile daily
   - Weekly auto-generate for ungenerated topics
   - Email summaries of new content

2. **Enhanced deduplication**
   - Detect near-duplicate articles
   - Merge similar subtopics
   - Clean up topic names

3. **Multi-language support**
   - French translations for Quebec
   - Bilingual article generation

4. **Export formats**
   - PDF generation
   - HTML templates
   - Email newsletter format

5. **Search functionality**
   - Full-text search across articles
   - Search by date range
   - Search generated articles

### Long-term Vision

1. **Web interface**
   - Flask/FastAPI backend
   - React frontend
   - Real-time generation status
   - Interactive hierarchy visualization

2. **AI-powered improvements**
   - Automatic subtopic merging suggestions
   - Related topics recommendations
   - Trend analysis (what's trending in legal news)

3. **Collaboration features**
   - Multi-user access
   - Comments on generated articles
   - Editorial workflow

4. **Analytics**
   - Track which topics get most views
   - Time-series analysis of legal trends
   - Geographic relevance scoring (by province)

---

## Current State Summary

**Database:**
- ✅ 60 articles fetched
- ✅ Topics ready for extraction (or already extracted)
- ✅ 3-level hierarchy support
- ✅ Generation tracking enabled

**Code:**
- ✅ All migrations run
- ✅ Control center fully functional
- ✅ Topic extraction with standard subtopics
- ✅ Generation with tracking
- ✅ Comprehensive documentation

**Next immediate action:**
Run `./setup_3_level_system.sh` to set up the 3-level hierarchy and reprocess articles.

---

## How to Continue This Project

When starting a new session, provide this context:

**"I'm continuing work on the Canadian Legal News Pipeline. The project is fully set up with a 3-level hierarchical topic system (Parent > Subtopic > Article Tag) and generation tracking to prevent duplicates.**

**Current state:**
- Database: `data/pipeline.db` with 60 articles
- Interfaces: `control_center.py` (main), `view_topics.py`, `generate.py`
- Documentation: See `COMMANDS_REFERENCE.md` and `3_LEVEL_HIERARCHY_GUIDE.md`

**I need help with:** [describe your specific task]

**Example tasks:**
- "Help me add generation status indicators to the hierarchy view"
- "I want to schedule daily automated fetching and processing"
- "Help me improve the synthesis prompt for better article quality"
- "I need to add search functionality to find topics by keyword"
- "How do I deploy this with cron jobs for automation?"

**Key files to reference:**
- `database.py` - All database operations
- `compile.py` - Topic extraction logic
- `generate.py` - Article synthesis logic
- `control_center.py` - Main user interface
- Database schema - See this document"

---

## Quick Reference Commands

```bash
# Launch control center (main interface)
python control_center.py

# Or run individual components
python fetch.py                          # Fetch new articles
python compile.py                        # Extract topics
python view_topics.py                    # Browse topics
python generate.py --topic 42            # Generate article

# Database operations
sqlite3 data/pipeline.db                 # Direct SQL access
python migration_add_hierarchy.py        # Add hierarchy support
python migration_add_article_tags_and_tracking.py  # Add tags & tracking

# Setup from scratch
./setup_3_level_system.sh                # Complete 3-level setup

# View documentation
cat COMMANDS_REFERENCE.md                # All commands
cat 3_LEVEL_HIERARCHY_GUIDE.md           # Hierarchy explanation
cat README.md                            # Project overview
```

---

## Contact Points for Issues

**Common error messages and solutions:**

- "GEMINI_API_KEY not found" → Add to `.env` file
- "Column 'article_tag' doesn't exist" → Run `migration_add_article_tags_and_tracking.py`
- "Table 'generated_articles' doesn't exist" → Run `migration_add_article_tags_and_tracking.py`
- "Rate limit exceeded" → Wait for quota reset or upgrade tier
- "Database is locked" → Close other instances of scripts

**Log files for debugging:**
- `logs/compile.log` - Topic extraction
- `logs/generate.log` - Article generation
- `logs/control_center.log` - Control center operations
- `logs/main.log` - Automated pipeline runs

---

**Last Updated:** 2026-01-20

**Project Status:** ✅ Production Ready

**Total Implementation Time:** ~4 hours

**Total Cost to Process 60 Articles:** ~$0.06 (topic extraction)

**Average Cost per Generated Article:** $0.12 (Sonnet) or $0.01 (Haiku)
