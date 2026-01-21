# Complete Command Reference - Hierarchical Topic System

## Quick Start (First Time Setup)

```bash
# 1. Reset database and run migration (already done!)
sqlite3 data/pipeline.db "DELETE FROM article_topics; DELETE FROM topics; UPDATE articles SET processed = 0;"
python migration_add_hierarchy.py

# 2. Extract hierarchical topics from all articles
python compile.py

# 3. View the hierarchy
python view_topics.py
```

---

## Core Pipeline Commands

### 1. Fetch Articles (`fetch.py`)

Collects articles from Canadian legal news sources.

```bash
# Fetch new articles from all sources
python fetch.py
```

**What it does:**
- Scrapes Slaw, McCarthy Tétrault, Monkhouse Law, etc.
- Stores articles in database with `processed=0`
- Skips duplicates automatically

**When to use:** Run daily/weekly to get fresh articles

---

### 2. Extract Topics (`compile.py`)

Uses Gemini AI to extract parent topics + subtopics from articles.

```bash
# Process all unprocessed articles
python compile.py
```

**What it does:**
- Reads articles with `processed=0`
- Sends to Gemini AI for hierarchical topic extraction
- Creates parent topics (e.g., "Employment Law")
- Creates subtopics (e.g., "Wrongful Dismissal")
- Links articles to subtopics
- Marks articles as `processed=1`

**Output example:**
```
Processing 60 articles...
✓ Extracted topics: Employment Law > Wrongful Dismissal, Employment Law > Workplace Safety
✓ Extracted topics: Contract Law > Breach of Contract
...
Total articles processed: 60
Successful: 60
Failed: 0
```

**Cost:** ~$0.001 per article (~$0.06 for 60 articles)

**When to use:** After running `fetch.py` or after resetting database

---

### 3. View Topics (`view_topics.py`)

Interactive browser for exploring topics and articles.

```bash
# Launch interactive topic browser
python view_topics.py
```

**Menu Options:**

#### Option 1: View Topics by Hierarchy (Tree View) ⭐ NEW!

Shows parent topics with subtopics indented underneath.

```
TOPICS BY CATEGORY
================================================================================

Employment Law (10/10 SMB) - 11 articles [ID: 1]
├── Wrongful Dismissal (9/10) - 3 articles [ID: 2]
├── Harassment & Discrimination (9/10) - 4 articles [ID: 3]
└── Workplace Safety (9/10) - 2 articles [ID: 4]

Contract Law (10/10 SMB) - 8 articles [ID: 6]
├── Contract Formation (9/10) - 3 articles [ID: 7]
└── Breach of Contract (9/10) - 3 articles [ID: 8]
```

**Use this to:**
- See how topics are organized
- Get topic IDs for generation
- Count articles per category

#### Option 2: View All Topics (Flat Table)

Shows all subtopics in a sortable table.

**Sort options:**
- Article count (most articles first)
- SMB relevance score (highest first)
- Most recent
- Alphabetical

#### Option 3: Filter Topics by SMB Score

Show only topics with minimum SMB relevance.

```
Enter minimum SMB relevance score (0-10):
Minimum score: 8

Topics with SMB score >= 8:
[Shows only highly relevant topics]
```

#### Option 4: Filter Topics by Article Count

Show only topics with minimum number of articles.

```
Enter minimum number of articles:
Minimum articles: 3

Topics with at least 3 articles:
[Shows well-covered topics]
```

#### Option 5: View Articles for Specific Topic

See all articles discussing a specific topic.

```
Enter topic ID (or 0 to cancel): 2

Articles for: Wrongful Dismissal (3 articles)
================================================================================

1. New Employment Standards Coming in 2025
   Source: Monkhouse Law | Published: 2025-01-15
   URL: https://monkhouselaw.com/...
   Summary: Ontario introduces new employment standards...

2. Wrongful Dismissal Case Analysis
   Source: Slaw | Published: 2025-01-12
   URL: https://slaw.ca/...
```

#### Option 6: Show Database Statistics

View pipeline statistics.

```
DATABASE STATISTICS
Total Articles:       60
Processed Articles:   60
Unprocessed Articles: 0
Total Topics:         35
Total Links:          120
Avg Articles/Topic:   3.4

Top 5 Topics by Article Count:
  1. Employment Standards (5 articles, SMB: 9)
  2. Data Privacy (4 articles, SMB: 8)
  3. Contract Formation (4 articles, SMB: 9)
  4. Corporate Governance (3 articles, SMB: 7)
  5. Tax Compliance (3 articles, SMB: 9)
```

#### Option 7: Export Topic List (for generate.py)

Create a file with topic IDs for batch generation.

**Filter options:**
1. All topics
2. SMB score >= 8
3. SMB score >= 8 AND article count >= 3
4. Custom filter

**Output:** `topics_to_generate.txt`
```
2
3
7
8
15
```

**Use with:** `python generate.py --topics-file topics_to_generate.txt`

---

### 4. Generate Articles (`generate.py`)

Synthesizes source articles into comprehensive SMB-focused articles using Claude AI.

---

## Generation Commands (All Options)

### A. Generate by Subtopic (Focused Article)

Generate article about ONE specific subtopic.

```bash
# Generate article for subtopic ID 2 (Wrongful Dismissal)
python generate.py --topic 2
```

**What it does:**
- Fetches all articles tagged with subtopic ID 2
- Sends to Claude for synthesis
- Creates focused article on that subtopic only

**Output:**
```
output/generated_articles/wrongful_dismissal_2026_01_20.md
```

**Use when:** You want deep dive on specific issue

---

### B. Generate by Parent Topic (Comprehensive Article)

Generate comprehensive article from ALL subtopics under a parent.

```bash
# Generate comprehensive Employment Law article (all subtopics)
python generate.py --parent 1
```

**What it does:**
- Finds all subtopics under parent ID 1
- Fetches articles from ALL subtopics
- Combines into comprehensive overview

**Example:**
- Parent: Employment Law (ID: 1)
- Includes: Wrongful Dismissal + Harassment + Workplace Safety + Standards
- Result: Comprehensive "Employment Law for SMBs" article

**Output:**
```
output/generated_articles/employment_law_2026_01_20.md
```

**Use when:** You want comprehensive category overview

---

### C. Combine Specific Subtopics

Generate article combining SELECTED subtopics.

```bash
# Combine Wrongful Dismissal (ID: 2) + Employment Standards (ID: 5)
python generate.py --subtopics 2 5
```

**What it does:**
- Fetches articles from both subtopics
- Deduplicates (if same article tagged with both)
- Synthesizes into single article

**Output:**
```
output/generated_articles/wrongful_dismissal_employment_standards_2026_01_20.md
```

**Use when:** You want custom combination of related topics

---

### D. Generate Multiple Articles (Batch)

Generate separate article for each topic ID.

```bash
# Generate 3 separate articles
python generate.py --topics 2 5 7
```

**What it does:**
- Generates article for topic 2
- Generates article for topic 5
- Generates article for topic 7
- Creates 3 separate output files

**Output:**
```
output/generated_articles/wrongful_dismissal_2026_01_20.md
output/generated_articles/employment_standards_2026_01_20.md
output/generated_articles/contract_formation_2026_01_20.md
```

**Use when:** You want multiple separate articles

---

### E. Generate from File (Batch)

Generate articles for all topic IDs in a file.

```bash
# 1. Export topics from view_topics.py (Option 7)
#    Creates: topics_to_generate.txt

# 2. Generate articles for all topics in file
python generate.py --topics-file topics_to_generate.txt
```

**topics_to_generate.txt format:**
```
2
5
7
9
12
```

**Use when:** You have a curated list of topics to generate

---

### F. Choose AI Model

All generation commands support model selection.

```bash
# Use Claude Sonnet 3.5 (best quality, ~$0.12/article) - DEFAULT
python generate.py --topic 2 --model sonnet

# Use Claude Haiku 3.5 (faster, cheaper, ~$0.01/article)
python generate.py --topic 2 --model haiku
```

**Model Comparison:**
- **Sonnet:** Best quality, professional tone, comprehensive synthesis
- **Haiku:** 12x cheaper, faster, good quality for straightforward topics

---

## Common Workflows

### Workflow 1: Weekly Legal Update

Generate comprehensive articles for top categories.

```bash
# 1. View hierarchy to identify parent IDs
python view_topics.py
# Choose option 1, note parent IDs

# 2. Generate comprehensive articles
python generate.py --parent 1    # Employment Law
python generate.py --parent 6    # Contract Law
python generate.py --parent 10   # Privacy & Data Protection

# Result: 3 comprehensive articles covering multiple subtopics each
```

---

### Workflow 2: Targeted Deep Dive

Focus on emerging issue with multiple articles.

```bash
# 1. View topics to find subtopic ID
python view_topics.py
# Choose option 2, filter by article count >= 3

# 2. Generate focused article
python generate.py --topic 15   # AI Regulation (5 articles)

# Result: Deep dive on AI Regulation combining 5 source articles
```

---

### Workflow 3: Custom Newsletter

Create custom combination for client newsletter.

```bash
# 1. Identify relevant subtopics
python view_topics.py
# Browse hierarchy, note IDs: 2, 3, 5

# 2. Combine into single article
python generate.py --subtopics 2 3 5

# Result: "HR Legal Essentials" combining Wrongful Dismissal + Harassment + Standards
```

---

### Workflow 4: Batch Generation

Generate multiple articles efficiently.

```bash
# 1. Export high-value topics
python view_topics.py
# Choose option 7 (Export)
# Filter: SMB score >= 8 AND article count >= 3
# Creates: topics_to_generate.txt

# 2. Batch generate
python generate.py --topics-file topics_to_generate.txt --model haiku

# Result: Multiple articles generated from filtered topics
```

---

## Database Commands

### View Database Stats

```bash
sqlite3 data/pipeline.db "
SELECT
    'Total Articles:' as stat, COUNT(*) as value FROM articles
UNION ALL
SELECT
    'Processed Articles:', COUNT(*) FROM articles WHERE processed = 1
UNION ALL
SELECT
    'Parent Topics:', COUNT(*) FROM topics WHERE is_parent = 1
UNION ALL
SELECT
    'Subtopics:', COUNT(*) FROM topics WHERE is_parent = 0;
"
```

### View Hierarchy in SQL

```bash
sqlite3 data/pipeline.db "
SELECT
    p.topic_name as Parent,
    s.topic_name as Subtopic,
    s.smb_relevance_score as Score,
    COUNT(at.article_id) as Articles
FROM topics p
LEFT JOIN topics s ON s.parent_topic_id = p.id
LEFT JOIN article_topics at ON s.id = at.topic_id
WHERE p.is_parent = 1
GROUP BY p.id, s.id
ORDER BY p.topic_name, Articles DESC;
"
```

### Reset Topics (Keep Articles)

```bash
# Clear topics but keep articles for reprocessing
sqlite3 data/pipeline.db "
DELETE FROM article_topics;
DELETE FROM topics;
UPDATE articles SET processed = 0;
"

# Then rerun
python compile.py
```

### Complete Reset

```bash
# Delete everything and start fresh
sqlite3 data/pipeline.db "
DELETE FROM article_topics;
DELETE FROM topics;
DELETE FROM articles;
"

# Then fetch and process
python fetch.py
python compile.py
```

---

## Troubleshooting Commands

### Check Migration Status

```bash
sqlite3 data/pipeline.db "PRAGMA table_info(topics);"
```

**Look for:**
- `parent_topic_id` column
- `is_parent` column

### View Sample Topics

```bash
sqlite3 data/pipeline.db "
SELECT
    id,
    topic_name,
    parent_topic_id,
    is_parent,
    smb_relevance_score
FROM topics
LIMIT 10;
"
```

### Find Orphaned Subtopics

```bash
sqlite3 data/pipeline.db "
SELECT * FROM topics
WHERE is_parent = 0 AND parent_topic_id IS NULL;
"
```

**Should return 0 rows** (no orphans if properly processed)

### View Logs

```bash
# View compile log (topic extraction)
tail -f logs/compile.log

# View generate log (article synthesis)
tail -f logs/generate.log
```

---

## Cost Estimates

### Compile (Gemini 2.5 Flash)
- Per article: ~$0.001
- 60 articles: ~$0.06
- 1,000 articles: ~$1.00

### Generate (Claude Sonnet 3.5)
- Per article: ~$0.12
- 10 articles: ~$1.20

### Generate (Claude Haiku 3.5)
- Per article: ~$0.01
- 10 articles: ~$0.10

---

## Quick Reference

```bash
# SETUP (one time)
python migration_add_hierarchy.py

# DAILY WORKFLOW
python fetch.py                      # Get new articles
python compile.py                    # Extract topics
python view_topics.py                # Browse topics
python generate.py --parent 1        # Generate article

# GENERATION OPTIONS
--topic 2              # Single subtopic
--parent 1             # All subtopics under parent
--subtopics 2 5        # Combine specific subtopics
--topics 2 5 7         # Multiple separate articles
--topics-file file.txt # Batch from file
--model haiku          # Use cheaper model
```

---

**Ready to use! Start with:**
```bash
python compile.py
```

This will process your 60 articles with the new hierarchical structure.
