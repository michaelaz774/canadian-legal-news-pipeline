"""
Configuration module for Canadian Legal News Pipeline
Central source definitions and settings

WHY SEPARATE CONFIGURATION:
- Easy to add/remove sources without touching fetch.py code
- All source URLs in one place for maintenance
- Can enable/disable sources by commenting out entries
- Clear separation between "what to fetch" (config) and "how to fetch" (fetch.py)

SOURCE TYPES EXPLAINED:
1. RSS: Simple XML feeds, easiest to parse (feedparser handles everything)
2. API: Structured JSON responses, requires API keys
3. Scrape: HTML parsing, requires CSS selectors (most fragile, changes with site updates)
"""

# ============================================================================
# NEWS SOURCES
# Starting with 5-10 high-value sources for MVP
# ============================================================================

SOURCES = [
    # ========================================================================
    # RSS FEEDS - Easy, High Value
    # ========================================================================
    # RSS is the easiest source type because:
    # - Standardized XML format
    # - Designed specifically for content syndication
    # - Includes title, link, summary, published date automatically
    # - feedparser library handles all parsing
    #
    # HOW TO FIND RSS FEEDS:
    # - Look for RSS icon on website
    # - Try adding /feed/ or /rss/ to domain
    # - View page source and search for "rss" or "application/rss+xml"
    # ========================================================================

    {
        'name': 'Slaw',
        'type': 'rss',
        'url': 'https://www.slaw.ca/feed/',
        'category': 'legal_magazine',
        'description': 'General Canadian legal commentary and analysis'
    },
    # ABOUT SLAW:
    # - Leading Canadian legal blog
    # - Broad coverage: all areas of law
    # - High quality analysis
    # - Updates daily

    {
        'name': 'Michael Geist',
        'type': 'rss',
        'url': 'http://www.michaelgeist.ca/feed/',
        'category': 'technology_law',
        'description': 'Technology law, copyright, privacy'
    },
    # ABOUT MICHAEL GEIST:
    # - Leading expert on Canadian tech law
    # - Focus: copyright, privacy, internet regulation
    # - Highly relevant for tech-focused SMBs

    {
        'name': 'McCarthy Tétrault - Employer Advisor',
        'type': 'rss',
        'url': 'https://www.mccarthy.ca/en/insights/blogs/canadian-employer-advisor/rss.xml',
        'category': 'employment_law',
        'description': 'Employment law updates for employers'
    },
    # ABOUT MCCARTHY TÉTRAULT:
    # - Major Canadian law firm
    # - Employer-focused employment law blog
    # - Very relevant for SMBs with employees

    {
        'name': 'Monkhouse Law',
        'type': 'rss',
        'url': 'https://www.monkhouselaw.com/feed/',
        'category': 'employment_law',
        'description': 'Employment law from employee perspective'
    },
    # ABOUT MONKHOUSE:
    # - Employee-side employment law firm
    # - Good for understanding risks SMBs face
    # - Complements McCarthy's employer perspective

    {
        'name': 'Rudner Law',
        'type': 'rss',
        'url': 'https://www.rudnerlaw.ca/feed/',
        'category': 'employment_law',
        'description': 'Employment law commentary'
    },
    # ABOUT RUDNER:
    # - Employment law specialists
    # - Regular updates on cases and legislation
    # - Practical guidance for employers

    # ========================================================================
    # API SOURCES - Structured Data
    # ========================================================================
    # APIs are great because:
    # - Structured JSON responses (easy to parse)
    # - Designed for programmatic access
    # - More reliable than scraping
    # - Often include metadata (dates, categories, etc.)
    #
    # TRADEOFF:
    # - Requires API key (free registration)
    # - May have rate limits
    # - Need to read API documentation
    # ========================================================================

    # CanLII API - Multiple databases for different courts
    # Documentation: https://www.canlii.org/en/info/api.html
    #
    # DATABASE IDs EXPLAINED:
    # - 'csc-scc': Supreme Court of Canada (highest court, nationwide precedent)
    # - 'onca': Ontario Court of Appeal (provincial appeals)
    # - 'bcca': British Columbia Court of Appeal
    # - 'abca': Alberta Court of Appeal
    #
    # We query multiple databases separately to get comprehensive coverage

    {
        'name': 'CanLII - Supreme Court',
        'type': 'api',
        'url': 'https://api.canlii.org/v1/caseBrowse/en/csc-scc/',
        'api_key_env': 'CANLII_API_KEY',
        'database_id': 'csc-scc',
        'category': 'case_law',
        'description': 'Recent Supreme Court of Canada decisions'
    },
    {
        'name': 'CanLII - Ontario Court of Appeal',
        'type': 'api',
        'url': 'https://api.canlii.org/v1/caseBrowse/en/onca/',
        'api_key_env': 'CANLII_API_KEY',
        'database_id': 'onca',
        'category': 'case_law',
        'description': 'Recent Ontario Court of Appeal decisions'
    },
    # ABOUT CANLII API:
    # - Free API for Canadian case law
    # - Register at: https://www.canlii.org/en/info/api.html
    # - Returns recent decisions from all Canadian courts
    # - Includes case metadata (court, date, keywords)
    #
    # API USAGE:
    # - fetch.py reads CANLII_API_KEY from environment (.env file)
    # - Makes GET request with API key as parameter
    # - Parses JSON response
    # - Extracts: title, URL, snippet, date

    # ========================================================================
    # WEB SCRAPING - Last Resort
    # ========================================================================
    # Web scraping is used when:
    # - No RSS feed available
    # - No API available
    # - Only option is parsing HTML
    #
    # CHALLENGES:
    # - Fragile: Breaks when website design changes
    # - Need to inspect HTML and find CSS selectors
    # - May encounter anti-scraping measures
    # - Need to be respectful (don't overwhelm servers)
    #
    # CSS SELECTORS EXPLAINED:
    # - 'container': The repeating element that wraps each article/case
    #   Example: <div class="decision-row"> ... </div>
    # - 'title': Where to find the title within the container
    #   Example: <h3>Case Name</h3>
    # - 'link': Where to find the URL
    #   Example: <a href="/case/123">
    # - 'date': Where to find the date
    #   Example: <span class="date">2025-01-10</span>
    #
    # HOW TO FIND SELECTORS:
    # 1. Open website in browser
    # 2. Right-click on article → Inspect Element
    # 3. Find the parent container that wraps each article
    # 4. Note the class or tag name
    # 5. Find title, link, date elements within
    # ========================================================================

    {
        'name': 'Ontario Court of Appeal',
        'type': 'scrape',
        'url': 'https://coadecisions.ontariocourts.ca/coa/coa/en/nav_date.do',
        'category': 'case_law',
        'selectors': {
            'container': '.decision-row',  # Each case is in a .decision-row div
            'title': 'h3',                  # Title is in an h3 tag
            'link': 'a',                    # Link is in an anchor tag
            'date': '.date'                 # Date is in an element with .date class
        },
        'description': 'Recent decisions from Ontario Court of Appeal'
    },
    # ABOUT ONTARIO COURT OF APPEAL:
    # - Province's highest court (below Supreme Court of Canada)
    # - Important precedents for employment, corporate, contract law
    # - Highly relevant for Ontario-based SMBs
    #
    # NOTE: Selectors may need adjustment after inspecting actual HTML
    # Run fetch.py and check logs if this source returns no results

    {
        'name': 'Supreme Court of Canada',
        'type': 'scrape',
        'url': 'https://decisions.scc-csc.ca/scc-csc/scc-csc/en/nav_date.do',
        'category': 'case_law',
        'selectors': {
            'container': '.decision-item',   # Each case is in a .decision-item div
            'title': '.decision-title',      # Title in .decision-title
            'link': 'a',                     # Link in anchor tag
            'date': '.decision-date'         # Date in .decision-date
        },
        'description': 'Recent decisions from Supreme Court of Canada'
    },
    # ABOUT SUPREME COURT OF CANADA:
    # - Highest court in Canada
    # - Final word on legal interpretation
    # - Cases have nationwide impact
    # - Lower volume but highest importance
    #
    # NOTE: Selectors are estimates and may need adjustment

    # ========================================================================
    # FUTURE SOURCES (commented out for MVP)
    # ========================================================================
    # Uncomment these once core pipeline is working
    # Add more sources incrementally to avoid overwhelming the system
    #
    # {
    #     'name': 'Canadian Lawyer Magazine',
    #     'type': 'rss',
    #     'url': 'https://www.canadianlawyermag.com/rss/',
    #     'category': 'legal_news',
    #     'description': 'General legal news and practice management'
    # },
    #
    # {
    #     'name': 'Osgoode Hall Law School - IP Osgoode',
    #     'type': 'rss',
    #     'url': 'http://www.iposgoode.ca/feed/',
    #     'category': 'intellectual_property',
    #     'description': 'Intellectual property law blog'
    # },
    #
    # {
    #     'name': 'McMillan LLP - Business Law',
    #     'type': 'rss',
    #     'url': 'https://mcmillan.ca/feed/',
    #     'category': 'business_law',
    #     'description': 'Corporate and business law updates'
    # },
]

# ============================================================================
# SMB RELEVANCE FILTERING
# ============================================================================
# These lists guide the LLM (GPT-4) when scoring topics for SMB relevance
# Used in compile.py when extracting topics
#
# THE SCORING SYSTEM:
# - 8-10: Highly relevant (direct SMB impact, actionable)
# - 5-7: Moderately relevant (useful context, indirect impact)
# - 0-4: Low relevance (large enterprise, complex securities, international trade)
#
# WHY THIS MATTERS:
# - Not all legal news is relevant to small-medium businesses
# - Complex M&A or securities regulation is for large corporations
# - Employment law, contracts, tax directly impacts SMBs
# - Helps prioritize which topics to generate articles about
# ============================================================================

SMB_FOCUS_AREAS = [
    # These legal areas directly impact SMBs - score HIGH
    'employment law',           # Hiring, firing, workplace policies
    'corporate law',            # Business structure, governance
    'contract law',             # Commercial agreements, terms of service
    'intellectual property',    # Trademarks, copyright, trade secrets
    'tax law',                  # Corporate tax, HST/GST, deductions
    'compliance',               # Regulatory requirements
    'corporate governance',     # Board duties, shareholder rights
    'privacy law',              # PIPEDA, data protection
    'commercial law',           # Sales, leasing, commercial disputes
    'real estate',              # Commercial leases, property purchases
]
# EXAMPLES OF HIGH-RELEVANCE TOPICS:
# - "New wrongful dismissal case sets higher severance standards" → 9/10
# - "CRA clarifies remote work expense deductions" → 8/10
# - "Changes to PIPEDA privacy breach notification requirements" → 9/10

EXCLUDE_AREAS = [
    # These legal areas are NOT relevant to most SMBs - score LOW
    'complex M&A',              # Mergers & acquisitions (large enterprise)
    'securities law',           # Public company regulations (TSX/NYSE)
    'large enterprise',         # Matters specific to large corporations
    'international trade',      # Cross-border trade agreements
    'class actions',            # Large-scale litigation (not day-to-day)
    'constitutional law',       # Academic interest, not operational
    'criminal law',             # Not relevant to business operations
    'family law',               # Personal matters, not business
]
# EXAMPLES OF LOW-RELEVANCE TOPICS:
# - "New TSX listing requirements for public companies" → 2/10
# - "Constitutional challenge to federal law" → 1/10
# - "Class action certification requirements" → 3/10

# ============================================================================
# PIPELINE SETTINGS
# ============================================================================
# General configuration settings for the pipeline
# These can be overridden by environment variables in .env
# ============================================================================

# How often to fetch new articles (hours)
# Not used in MVP (manual runs only), but defined for future automation
FETCH_INTERVAL_HOURS = 6

# Maximum articles to fetch per source (prevents overwhelming the system)
MAX_ARTICLES_PER_SOURCE = 50

# Request timeout for web requests (seconds)
REQUEST_TIMEOUT = 30

# User agent for web scraping (identifies our bot to servers)
# Being transparent is good etiquette and avoids being blocked
USER_AGENT = 'CanadianLegalNewsPipeline/1.0 (Educational Research Bot)'

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
# Where to save log files
# Each phase (fetch, compile, generate) has its own log file
LOG_DIR = 'logs'

LOG_CONFIG = {
    'fetch': f'{LOG_DIR}/fetch.log',
    'compile': f'{LOG_DIR}/compile.log',
    'generate': f'{LOG_DIR}/generate.log',
}

# ============================================================================
# USAGE EXAMPLES
# ============================================================================
if __name__ == '__main__':
    """
    Test/demo script to show configuration contents.

    RUN THIS:
    python config.py

    This helps verify:
    - Configuration can be imported
    - All sources are properly formatted
    - No syntax errors
    """
    print("=" * 70)
    print("CANADIAN LEGAL NEWS PIPELINE - CONFIGURATION")
    print("=" * 70)

    print(f"\nTotal sources configured: {len(SOURCES)}")
    print("\nSources by type:")

    # Count sources by type
    from collections import Counter
    type_counts = Counter(source['type'] for source in SOURCES)
    for source_type, count in type_counts.items():
        print(f"  {source_type.upper()}: {count} sources")

    print("\n" + "-" * 70)
    print("SOURCE DETAILS:")
    print("-" * 70)

    for i, source in enumerate(SOURCES, 1):
        print(f"\n{i}. {source['name']}")
        print(f"   Type: {source['type'].upper()}")
        print(f"   Category: {source['category']}")
        print(f"   URL: {source['url']}")

        if source['type'] == 'api':
            print(f"   API Key: ${source.get('api_key_env', 'N/A')}")

        if source['type'] == 'scrape':
            print(f"   Selectors: {list(source['selectors'].keys())}")

        if 'description' in source:
            print(f"   Description: {source['description']}")

    print("\n" + "-" * 70)
    print("SMB FOCUS AREAS:")
    print("-" * 70)
    for area in SMB_FOCUS_AREAS:
        print(f"  • {area}")

    print("\n" + "-" * 70)
    print("EXCLUDED AREAS (LOW SMB RELEVANCE):")
    print("-" * 70)
    for area in EXCLUDE_AREAS:
        print(f"  • {area}")

    print("\n" + "=" * 70)
    print("Configuration loaded successfully!")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Review source URLs and verify they're accessible")
    print("  2. For API sources: Register for API keys")
    print("  3. For scrape sources: Inspect HTML and verify selectors")
    print("  4. Run fetch.py to test data collection")
