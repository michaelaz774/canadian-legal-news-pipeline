# Canadian Legal News Pipeline

Automated system for collecting Canadian legal articles, extracting topics with AI, and generating synthesized SMB-focused content.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Cost Estimates](#cost-estimates)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Overview

This pipeline automates the process of:
1. **Collecting** legal articles from 8+ Canadian sources (RSS feeds, APIs, web scraping)
2. **Extracting** relevant legal topics using Google Gemini AI
3. **Synthesizing** comprehensive articles for SMB audiences using Anthropic Claude

**Target Audience**: Small and medium-sized business (SMB) owners who need accessible legal information without legal jargon.

**Key Value**: Combines insights from multiple sources (Slaw, Monkhouse Law, McCarthy Tétrault, Michael Geist, etc.) into single, comprehensive articles focused on practical business applications.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CANADIAN LEGAL NEWS PIPELINE                     │
└─────────────────────────────────────────────────────────────────────┘

PHASE 1: DATA COLLECTION (fetch.py)
┌─────────────────────────────────────────────────────────────────────┐
│  RSS Feeds (5)     │  CanLII API (2)   │  Web Scraping (2)        │
│  · Slaw            │  · Case Law       │  · Monkhouse Law         │
│  · McCarthy        │  · Legislation    │  · Rudner Law            │
│  · Michael Geist   │                   │                          │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │   SQLite DB     │ ← 60 articles collected
        │  (pipeline.db)  │
        └─────────┬───────┘
                  │
PHASE 4: TOPIC EXTRACTION (compile.py)
                  │
                  ▼
        ┌─────────────────┐
        │  Gemini 2.5     │ ← Ultra-cheap: $0.06/60 articles
        │     Flash       │    Structured JSON output
        └─────────┬───────┘
                  │
                  ▼
        ┌─────────────────┐
        │  35 Topics      │ ← Employment Law, Contract Law, etc.
        │  Extracted      │    SMB relevance scored 0-10
        └─────────┬───────┘
                  │
PHASE 5: TOPIC BROWSING (view_topics.py)
                  │
                  ▼
        ┌─────────────────┐
        │  Interactive    │ ← Filter, sort, export topics
        │    CLI Menu     │    Select for generation
        └─────────┬───────┘
                  │
PHASE 6: ARTICLE SYNTHESIS (generate.py)
                  │
                  ▼
        ┌─────────────────┐
        │ Claude Sonnet   │ ← Best quality: $0.12/article
        │   or Haiku      │    Combines multiple sources
        └─────────┬───────┘
                  │
                  ▼
        ┌─────────────────┐
        │  Generated      │ ← Markdown articles in
        │   Articles      │    output/generated_articles/
        └─────────────────┘

PHASE 7: ORCHESTRATION (main.py)
        ┌─────────────────┐
        │  One-command    │ ← Runs entire pipeline
        │   Automation    │    Suitable for cron/scheduled tasks
        └─────────────────┘
```

---

## Features

### ✅ Data Collection
- **8 sources**: 5 RSS feeds, 2 CanLII API endpoints, 2 scraped websites
- **Duplicate prevention**: URL-based deduplication at database level
- **Content extraction**: Full article text (not just summaries)
- **Idempotent**: Safe to run multiple times without duplicating data

### ✅ Topic Extraction (AI-Powered)
- **Google Gemini 2.5 Flash**: Ultra-cost-effective ($0.30/$2.50 per 1M tokens)
- **Structured output**: Guaranteed valid JSON with Pydantic validation
- **SMB-focused scoring**: Topics rated 0-10 for relevance to small businesses
- **Topic normalization**: Deduplicates variations ("Employment Law" = "employment law")
- **Automatic retries**: Handles rate limits with exponential backoff

### ✅ Article Synthesis (AI-Powered)
- **Anthropic Claude**: Superior long-form writing (Sonnet 3.5 or Haiku)
- **Multi-source synthesis**: Combines insights from 3-5 articles per topic
- **SMB-optimized**: Plain language, practical advice, actionable takeaways
- **Markdown output**: Ready for CMS, blog, or newsletter
- **Cost-effective**: ~$0.12/article (Sonnet) or ~$0.01/article (Haiku)

### ✅ Interactive Tools
- **Topic browser** (view_topics.py): Filter, sort, and explore extracted topics
- **Export functionality**: Generate topic lists for batch processing
- **Comprehensive statistics**: Track pipeline health and progress

---

## Requirements

### System Requirements
- Python 3.9+
- 500 MB disk space
- Internet connection

### API Keys (Free Tiers Available)
1. **Google Gemini API** (free tier: 20 requests/day)
   - Get key: https://aistudio.google.com/app/apikey
   - Used for: Topic extraction

2. **Anthropic Claude API** (paid, but cheap)
   - Get key: https://console.anthropic.com/
   - Used for: Article synthesis
   - Cost: ~$0.12/article (Sonnet) or ~$0.01/article (Haiku)

3. **CanLII API** (optional, free)
   - Get key: https://www.canlii.org/en/info/api.html
   - Used for: Canadian case law and legislation

---

## Installation

### 1. Clone or Download
```bash
cd ~/Desktop
# Ensure you're in the Automated_news_pipeline directory
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
```bash
cp .env.example .env
# Edit .env and add your API keys:
# GEMINI_API_KEY=your-gemini-key
# ANTHROPIC_API_KEY=your-anthropic-key
```

### 5. Verify Installation
```bash
python -c "from database import Database; db = Database(); print('✓ Database initialized'); db.close()"
```

---

## Configuration

### Environment Variables (.env)

```bash
# Google Gemini API (for topic extraction in Phase 4)
# Get free key at: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your-gemini-key-here

# Anthropic Claude API (for article synthesis in Phase 6)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# CanLII API (optional, for Canadian case law)
CANLII_API_KEY=your-canlii-key-here

# Fetch interval for automated runs (hours)
FETCH_INTERVAL_HOURS=6
```

### Sources Configuration (config.py)

The pipeline collects from 8 sources:

**RSS Feeds (5)**:
- Slaw: Canadian law blog
- McCarthy Tétrault: Business law insights
- Michael Geist: Technology law and policy
- Monkhouse Law: Employment law
- Rudner Law: Employment law

**CanLII API (2)**:
- Recent case law
- New legislation

**Web Scraping (2)**:
- Monkhouse Law blog
- Rudner Law blog

To modify sources, edit `config.py` and adjust the `SOURCES` dictionary.

---

## Usage

### Quick Start (Run Full Pipeline)

```bash
# Activate virtual environment
source venv/bin/activate

# Run entire pipeline
python main.py --auto-generate
```

This will:
1. Fetch new articles from all sources
2. Extract topics from unprocessed articles
3. Auto-select top 5 high-value topics (SMB score ≥ 8, ≥ 3 articles)
4. Generate synthesized articles

---

### Individual Phase Usage

#### Phase 1: Collect Articles

```bash
python fetch.py
```

**What it does**:
- Fetches articles from 8 sources
- Stores in `data/pipeline.db`
- Skips duplicates automatically

**Output**:
```
Fetching from Slaw...
  ✓ Inserted: 10 articles
Fetching from McCarthy Tétrault...
  ✓ Inserted: 5 articles
...
Summary: 60 inserted, 0 skipped, 0 errors
```

---

#### Phase 4: Extract Topics

```bash
python compile.py
```

**What it does**:
- Processes unprocessed articles
- Sends to Gemini AI for topic extraction
- Stores topics and relationships in database

**Output**:
```
Processing 60 articles...
Extracting topics: 100%|████████| 60/60 [03:30<00:00]
✓ Extracted topics: Employment Law, Contract Law
...
Successful: 15, Failed: 45 (rate limit hit)
```

**Note**: Free tier has 20 requests/day limit. Failed articles will be retried on next run.

---

#### Phase 5: Browse Topics

```bash
python view_topics.py
```

**Interactive menu**:
```
MAIN MENU
--------------------------------------------------------------------------------
1. View all topics
2. Filter topics by SMB score
3. Filter topics by article count
4. View articles for a specific topic
5. Show database statistics
6. Export topic list (for generate.py)
7. Exit
```

---

#### Phase 6: Generate Synthesized Articles

```bash
# Generate for single topic
python generate.py --topic 5

# Generate for multiple topics
python generate.py --topics 5 12 8

# Use cheaper/faster Haiku model
python generate.py --topic 5 --model haiku

# Generate from exported list
python generate.py --topics-file topics_to_generate.txt
```

**What it does**:
- Fetches all articles for the topic
- Sends to Claude for synthesis
- Saves Markdown file to `output/generated_articles/`

**Output**:
```
Processing topic ID 5...
✓ Article generated successfully
  Input tokens: 28,456
  Output tokens: 1,842
  Estimated cost: $0.1127
✓ Article saved to: output/generated_articles/employment_law_2026_01_20.md
  Word count: 1,842
```

---

### Automated Scheduling

#### Using Cron (Mac/Linux)

```bash
# Edit crontab
crontab -e

# Run pipeline daily at 2 AM
0 2 * * * cd /path/to/Automated_news_pipeline && /path/to/venv/bin/python main.py --auto-generate >> logs/cron.log 2>&1
```

#### Using Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 2:00 AM
4. Action: Start a program
5. Program: `C:\path\to\venv\Scripts\python.exe`
6. Arguments: `main.py --auto-generate`
7. Start in: `C:\path\to\Automated_news_pipeline`

---

## Cost Estimates

### Phase 4: Topic Extraction (Gemini 2.5 Flash)

| Volume | Input Cost | Output Cost | Total |
|--------|------------|-------------|-------|
| 60 articles | $0.03 | $0.03 | **$0.06** |
| 1,000 articles | $0.48 | $0.52 | **$1.00** |

**Free Tier**: 20 requests/day = 20 articles/day = 600 articles/month for **FREE**

---

### Phase 6: Article Synthesis

#### Claude Sonnet 3.5 (Best Quality)

| Volume | Input Cost | Output Cost | Total |
|--------|------------|-------------|-------|
| 1 article | $0.09 | $0.03 | **$0.12** |
| 10 articles | $0.90 | $0.30 | **$1.20** |
| 100 articles | $9.00 | $3.00 | **$12.00** |

#### Claude Haiku (Fast & Cheap)

| Volume | Input Cost | Output Cost | Total |
|--------|------------|-------------|-------|
| 1 article | $0.0075 | $0.0025 | **$0.01** |
| 10 articles | $0.075 | $0.025 | **$0.10** |
| 100 articles | $0.75 | $0.25 | **$1.00** |

---

### Monthly Pipeline Cost (Typical Usage)

**Scenario**: Process 1,000 articles → 50 synthesized articles/month

- Topic extraction: $1.00 (or FREE with daily runs)
- Article synthesis (Sonnet): $6.00
- **Total: ~$7.00/month**

**Budget Option** (Haiku): ~$1.50/month

---

## Project Structure

```
Automated_news_pipeline/
├── README.md                  # This file
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── .env                      # Your API keys (gitignored)
│
├── database.py               # Database operations (Phase 1)
├── config.py                 # Source configuration (Phase 1)
├── fetch.py                  # Article collection (Phase 1)
├── compile.py                # Topic extraction (Phase 4)
├── view_topics.py            # Topic browser (Phase 5)
├── generate.py               # Article synthesis (Phase 6)
├── main.py                   # Pipeline orchestration (Phase 7)
│
├── data/
│   └── pipeline.db           # SQLite database
│
├── logs/
│   ├── fetch.log             # Collection logs
│   ├── compile.log           # Extraction logs
│   ├── generate.log          # Synthesis logs
│   └── main.log              # Pipeline logs
│
├── output/
│   └── generated_articles/   # Synthesized Markdown files
│       ├── employment_law_2026_01_20.md
│       ├── contract_law_2026_01_21.md
│       └── ...
│
└── venv/                     # Virtual environment
```

---

## Troubleshooting

### Issue: Gemini Rate Limit Error

**Error**: `RESOURCE_EXHAUSTED: Quota exceeded for metric`

**Solution**:
- **Free tier**: 20 requests/day. Wait 24 hours or enable billing.
- **Enable billing**: https://console.cloud.google.com/billing
- **Alternative**: Switch to Claude Haiku for extraction (edit compile.py)

---

### Issue: No Articles Collected

**Possible causes**:
1. **Network issues**: Check internet connection
2. **Source changes**: Website structure changed (update scraper in fetch.py)
3. **Rate limiting**: Some sites limit requests

**Debug**:
```bash
python fetch.py
# Check logs/fetch.log for errors
```

---

### Issue: Topic Extraction Fails

**Error**: `GEMINI_API_KEY not found`

**Solution**:
```bash
# Verify .env file exists
cat .env | grep GEMINI_API_KEY

# If missing, add it
echo "GEMINI_API_KEY=your-key-here" >> .env
```

---

### Issue: Article Generation Fails

**Error**: `ANTHROPIC_API_KEY not found`

**Solution**:
```bash
# Get API key from https://console.anthropic.com/
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> .env
```

---

### Issue: Database Locked

**Error**: `database is locked`

**Solution**:
```bash
# Another process is using the database
# Kill hanging processes
ps aux | grep python
kill <process_id>
```

---

## Maintenance

### Database Management

#### Check Database Size
```bash
ls -lh data/pipeline.db
```

#### View Statistics
```bash
python -c "from database import Database; db = Database(); print(db.get_stats()); db.close()"
```

#### Reset Database (Caution: Deletes all data)
```bash
rm data/pipeline.db
python database.py  # Reinitialize
```

---

### Update Dependencies

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

---

### Monitor Costs

#### Track Gemini Usage
Visit: https://ai.dev/rate-limit

#### Track Claude Usage
Visit: https://console.anthropic.com/usage

---

### Backup Strategy

```bash
# Backup database
cp data/pipeline.db data/pipeline_backup_$(date +%Y%m%d).db

# Backup generated articles
tar -czf output_backup_$(date +%Y%m%d).tar.gz output/
```

---

## Advanced Usage

### Custom Topic Selection

```python
# Create custom topic list
from database import Database

db = Database()
topics = db.get_topics_with_metadata()

# Filter for high-value topics
selected = [t for t in topics if t['smb_relevance_score'] >= 9 and t['article_count'] >= 4]

# Save topic IDs
with open('high_priority_topics.txt', 'w') as f:
    for topic in selected:
        f.write(f"{topic['id']}\n")

db.close()
```

Then generate:
```bash
python generate.py --topics-file high_priority_topics.txt
```

---

### Extend Sources

Edit `config.py`:

```python
SOURCES = {
    # Add your custom source
    'my_custom_source': {
        'type': 'rss',
        'url': 'https://example.com/feed.xml',
        'enabled': True
    }
}
```

---

## License

This project is provided as-is for educational and commercial use.

---

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review this README's Troubleshooting section
3. Check environment variables in `.env`

---

**Built with**:
- Python 3.11
- SQLite 3
- Google Gemini 2.5 Flash
- Anthropic Claude 3.5
- Beautiful Soup, Feedparser, Requests

**Last Updated**: January 2026
