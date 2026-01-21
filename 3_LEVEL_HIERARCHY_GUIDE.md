# 3-Level Topic Hierarchy & Generation Tracking

## Overview

Your pipeline now supports a **3-level hierarchy** with **generation tracking** to avoid duplicates:

1. **Parent Topic** (Employment Law, Contract Law, etc.)
2. **Subtopic** (Wrongful Dismissal, Data Breach Response, etc.)
3. **Article Tag** (Specific aspect: "Wrongful dismissal during pregnancy leave")

Plus: **Automatic tracking** of which subtopics have been generated.

---

## The 3 Levels Explained

### Level 1: Parent Topic
**Broad legal category** - Used for browsing and organization

Examples:
- Employment Law
- Contract Law
- Privacy & Data Protection
- Technology & AI Law
- Tax Law

### Level 2: Subtopic
**Standard category for grouping** - Used for article generation

Examples under Employment Law:
- Wrongful Dismissal
- Workplace Harassment & Discrimination
- Employment Contracts & Termination
- Severance & Termination Pay

**Multiple articles** with the same subtopic will be combined when generating.

### Level 3: Article Tag
**Specific aspect discussed in each article** - Helps differentiate articles

Examples under "Wrongful Dismissal":
- "Wrongful dismissal during pregnancy leave"
- "Constructive dismissal hostile work environment"
- "Severance pay calculations for wrongful dismissal"
- "Employee duty to mitigate damages"

**Same subtopic, different angles** - All get synthesized into one comprehensive article.

---

## Example Structure

```
Employment Law (Parent)
├── Wrongful Dismissal (Subtopic) - 15 articles
│   ├── Article 1: "Wrongful dismissal during pregnancy leave"
│   ├── Article 2: "Constructive dismissal hostile work environment"
│   ├── Article 3: "Severance pay calculations"
│   ├── Article 4: "Employee duty to mitigate damages"
│   └── ... (11 more articles with different tags)
│
├── Workplace Harassment & Discrimination (Subtopic) - 8 articles
│   ├── Article 1: "Religious discrimination prevention"
│   ├── Article 2: "Pregnancy-based discrimination"
│   └── ... (6 more articles)
│
└── Severance & Termination Pay (Subtopic) - 10 articles
    ├── Article 1: "EI benefit eligibility changes"
    ├── Article 2: "Layoff vs termination legal definitions"
    └── ... (8 more articles)
```

---

## Generation Tracking

### How It Works

When you generate an article:
1. Article is created and saved
2. Entry is added to `generated_articles` table
3. Future generations will **skip** that subtopic automatically

### What Gets Tracked

For each generated article:
- **Topic ID** (subtopic that was generated)
- **Generated date** (when it was created)
- **Output file** (path to the markdown file)
- **Model used** (sonnet or haiku)
- **Source article count** (how many articles were synthesized)
- **Word count** (length of generated article)

### Benefits

✅ **Avoid duplicates** - Won't regenerate the same topic
✅ **Track history** - See what's been generated
✅ **Smart suggestions** - Auto-generate only shows ungenerated topics
✅ **Progress tracking** - Know what's left to generate

---

## Setup Steps

### Step 1: Run New Migration

```bash
python migration_add_article_tags_and_tracking.py
```

This adds:
- `article_tag` column to `article_topics` table
- `generated_articles` table for tracking

### Step 2: Reset and Reprocess

Since you already processed with the old schema, reset and reprocess:

**Option A: Control Center (Easiest)**
```bash
python control_center.py
# Choose: 5 (Database) → 2 (Reset topics)
# Then: 2 (Process articles)
```

**Option B: Command Line**
```bash
sqlite3 data/pipeline.db "DELETE FROM article_topics; DELETE FROM topics; UPDATE articles SET processed = 0;"
python compile.py
```

### Step 3: View Results

```bash
python control_center.py
# Choose: 3 (View Topics) → 1 (Hierarchy)
```

---

## Expected Results

### Before (Old 2-Level System)
```
Employment Law - 53 articles
├── Wrongful Dismissal Risks (1 article)
├── Wrongful dismissal litigation costs (1 article)
├── Wrongful dismissal risks (1 article) ← duplicate!
├── Wrongful Dismissal Claims (1 article)
└── ... (49 more fragmented subtopics)
```

### After (New 3-Level System)
```
Employment Law - 53 articles
├── Wrongful Dismissal (15 articles) ✅ Grouped!
│   [Various tags: pregnancy leave, constructive dismissal, etc.]
├── Workplace Harassment & Discrimination (8 articles)
├── Employment Contracts & Termination (12 articles)
├── Severance & Termination Pay (10 articles)
└── Employment Standards & Leaves (8 articles)
```

---

## Using Generation Tracking

### View Ungenerated Topics

```bash
python control_center.py
# 3 (View Topics) → Select filters
```

Topics will show:
- ✅ Generated (date shown)
- ⚠️ Not generated yet

### Auto-Generate (Skips Generated)

```bash
python control_center.py
# 4 (Generate) → 4 (Auto-generate)
```

This will:
1. Find high-value ungenerated subtopics
2. Show you the list
3. Generate only NEW topics (skips already generated)

### Check Generation Status

```bash
python control_center.py
# 5 (Database) → 1 (Statistics)
```

Shows:
- Total generated articles
- Which topics have been generated
- When they were generated

---

## Database Schema

### article_topics table
```sql
CREATE TABLE article_topics (
    article_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL,
    article_tag TEXT,  -- NEW: Specific aspect discussed
    created_date TEXT NOT NULL,
    PRIMARY KEY (article_id, topic_id)
);
```

### generated_articles table
```sql
CREATE TABLE generated_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,  -- Subtopic that was generated
    generated_date TEXT NOT NULL,
    output_file TEXT NOT NULL,
    model_used TEXT NOT NULL,
    source_article_count INTEGER NOT NULL,
    word_count INTEGER,
    FOREIGN KEY (topic_id) REFERENCES topics(id)
);
```

---

## Querying Generation Status

### Check if topic generated
```sql
SELECT COUNT(*) FROM generated_articles WHERE topic_id = 42;
```

### Get all generated topics
```sql
SELECT
    t.topic_name,
    g.generated_date,
    g.model_used,
    g.source_article_count
FROM generated_articles g
JOIN topics t ON g.topic_id = t.id
ORDER BY g.generated_date DESC;
```

### Get ungenerated subtopics with >= 5 articles
```sql
SELECT
    t.topic_name,
    COUNT(at.article_id) as article_count
FROM topics t
LEFT JOIN article_topics at ON t.id = at.topic_id
WHERE t.is_parent = 0
  AND t.id NOT IN (SELECT topic_id FROM generated_articles)
GROUP BY t.id
HAVING COUNT(at.article_id) >= 5
ORDER BY article_count DESC;
```

---

## Standard Subtopics by Parent

### Employment Law
- Wrongful Dismissal
- Workplace Harassment & Discrimination
- Employment Contracts & Termination
- Employee Classification & Rights
- Workplace Safety & Accommodation
- Severance & Termination Pay
- Employment Standards & Leaves

### Contract Law
- Contract Formation & Interpretation
- Breach of Contract
- Restrictive Covenants
- Service Agreements

### Privacy & Data Protection
- Data Breach Response
- PIPEDA Compliance
- AI & Data Governance
- Government Data Access

### Tax Law
- Corporate Tax
- CRA Assessments & Appeals
- Digital Services Tax
- Payroll Tax

### Technology & AI Law
- AI Regulation & Compliance
- AI Liability & Ethics
- Digital Communications

### Corporate Governance
- Director & Officer Duties
- Shareholder Rights
- Corporate Compliance

### Intellectual Property
- Copyright
- Trademarks
- Trade Secrets

---

## Benefits of 3-Level System

### 1. Better Organization
- **Parent**: Browse by category
- **Subtopic**: Logical groupings
- **Article tag**: See what each article contributes

### 2. Comprehensive Generation
- **15 articles** on "Wrongful Dismissal" → One comprehensive guide
- **Not** 15 separate fragmented articles

### 3. No Duplicates
- Automatic tracking prevents regenerating same topic
- Can regenerate if needed (track history)

### 4. Efficient Workflow
- See what needs generation
- Focus on high-value ungenerated topics
- Track progress

### 5. Better Quality
- More source articles per generation
- Diverse perspectives combined
- Comprehensive coverage

---

## Workflow Example

### 1. Process Articles
```bash
python control_center.py → 2 (Process articles)
```

Result:
```
✓ Extracted topics: Employment Law > Wrongful Dismissal [Wrongful dismissal during pregnancy leave]
✓ Extracted topics: Employment Law > Wrongful Dismissal [Constructive dismissal hostile work environment]
✓ Extracted topics: Employment Law > Severance & Termination Pay [EI benefit eligibility changes]
```

### 2. View Hierarchy
```bash
python control_center.py → 3 (View) → 1 (Hierarchy)
```

Result:
```
Employment Law (10/10 SMB) - 53 articles
├── Wrongful Dismissal (9/10) - 15 articles [ID: 42] ⚠️ Not generated
├── Workplace Harassment & Discrimination (9/10) - 8 articles [ID: 43] ⚠️ Not generated
└── Severance & Termination Pay (9/10) - 10 articles [ID: 44] ⚠️ Not generated
```

### 3. Generate Article
```bash
python control_center.py → 4 (Generate) → 1 (By subtopic)
Enter subtopic ID: 42
```

Result:
```
✅ Generated: wrongful_dismissal_2026_01_20.md
   Sources: 15 articles
   Words: 2,341
   Tracked in database
```

### 4. Check Status
```bash
python control_center.py → 3 (View) → 1 (Hierarchy)
```

Result:
```
Employment Law (10/10 SMB) - 53 articles
├── Wrongful Dismissal (9/10) - 15 articles [ID: 42] ✅ Generated (2026-01-20)
├── Workplace Harassment & Discrimination (9/10) - 8 articles [ID: 43] ⚠️ Not generated
└── Severance & Termination Pay (9/10) - 10 articles [ID: 44] ⚠️ Not generated
```

---

## Ready to Start!

```bash
# 1. Run migration
python migration_add_article_tags_and_tracking.py

# 2. Reset and reprocess
python control_center.py
# → 5 (Database) → 2 (Reset topics)
# → 2 (Process articles)

# 3. View beautiful hierarchy
python control_center.py
# → 3 (View) → 1 (Hierarchy)

# 4. Generate your first article!
python control_center.py
# → 4 (Generate) → 1 (By subtopic)
```

Your articles will now be **comprehensive, well-organized, and never duplicated**! 🎉
