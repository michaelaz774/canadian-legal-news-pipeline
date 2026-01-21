"""
Fetch Articles Page
Triggers article fetching from Canadian legal news sources
"""

import streamlit as st
import sys
import os
import time
from database import Database
from utils.subprocess_runner import run_pipeline_script_streaming, parse_fetch_output
from utils.auth import check_password

st.set_page_config(page_title="Fetch Articles", page_icon="📥", layout="wide")

# Authentication check
if not check_password():
    st.stop()

# Initialize refresh trigger if not exists
if 'refresh_trigger' not in st.session_state:
    st.session_state.refresh_trigger = 0

st.title("📥 Fetch Articles")
st.markdown("Scrape new articles from Canadian legal news sources")

st.markdown("---")

# ============================================================================
# CURRENT STATUS
# ============================================================================

st.markdown("### 📊 Current Status")

try:
    db = Database()
    stats = db.get_stats()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Articles", stats['total_articles'])

    with col2:
        st.metric("Unprocessed Articles", stats['unprocessed_articles'])

    with col3:
        processing_rate = 0
        if stats['total_articles'] > 0:
            processing_rate = round((stats['total_articles'] - stats['unprocessed_articles']) / stats['total_articles'] * 100, 1)
        st.metric("Processing Rate", f"{processing_rate}%")

    db.close()

except Exception as e:
    st.error(f"Error loading stats: {e}")

st.markdown("---")

# ============================================================================
# DATA SOURCES
# ============================================================================

st.markdown("### 📰 Data Sources")

st.markdown("""
The fetch script scrapes articles from the following Canadian legal sources:

- **Slaw** - Canadian legal blog with diverse legal commentary
- **McCarthy Tétrault** - Law firm insights and analysis
- **Monkhouse Law** - Employment law expertise
- **CanLII** - Canadian Legal Information Institute (case law)

Each source provides RSS feeds that are parsed to extract articles.
""")

st.info("💡 **Tip:** Running fetch multiple times is safe - duplicate articles are automatically skipped!")

st.markdown("---")

# ============================================================================
# FETCH OPERATION
# ============================================================================

st.markdown("### 🚀 Fetch New Articles")

st.markdown("""
Click the button below to fetch new articles. This process:
1. Connects to each data source
2. Parses RSS feeds
3. Extracts article content
4. Saves to database (skipping duplicates)

**Estimated time:** 30-60 seconds
""")

if st.button("🔄 Fetch Articles Now", type="primary", use_container_width=True):
    st.markdown("### 🔄 Fetching Articles")
    st.markdown("Watch the live progress below.")
    st.markdown("---")

    # Run fetch.py with real-time streaming output
    success, stdout, stderr = run_pipeline_script_streaming("fetch.py", timeout=300)

    if success:
        st.markdown("---")

        # Parse output to show statistics
        fetch_stats = parse_fetch_output(stdout)

        if fetch_stats['inserted'] > 0 or fetch_stats['skipped'] > 0:
            st.markdown("### 📊 Fetch Results")
            col_inserted, col_skipped = st.columns(2)

            with col_inserted:
                st.metric(
                    "New Articles Inserted",
                    fetch_stats['inserted'],
                    help="New articles added to database"
                )

            with col_skipped:
                st.metric(
                    "Duplicates Skipped",
                    fetch_stats['skipped'],
                    help="Articles already in database"
                )

        # Show success message and auto-refresh
        if fetch_stats['inserted'] > 0:
            st.success("📊 Database updated! Refreshing stats...")
            st.balloons()
            # Increment refresh trigger to force sidebar update
            st.session_state.refresh_trigger += 1
            time.sleep(1)  # Brief pause to show success message
            st.rerun()  # Auto-refresh to show updated stats
        else:
            st.info("No new articles found. All sources are up to date.")

st.markdown("---")

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

with st.expander("🔧 Troubleshooting"):
    st.markdown("""
    **Common Issues:**

    1. **Timeout errors** - Some sources may be slow. The script will continue with available sources.

    2. **Network errors** - Check your internet connection. The script will retry failed sources.

    3. **All articles skipped** - This means no new articles are available. Try again later.

    4. **Parsing errors** - Some RSS feeds may change format. Check logs for details.

    **What to do if fetch fails:**
    - Check the error log above for specific issues
    - Verify internet connection
    - Try running fetch.py manually: `python fetch.py`
    - Check if sources are accessible in your browser
    """)

# ============================================================================
# NEXT STEPS
# ============================================================================

st.markdown("### ➡️ Next Steps")

st.info("""
After fetching articles:
1. Go to **⚙️ Process Topics** to extract topics from new articles
2. Use **📁 Browse Topics** to explore the hierarchy
3. Select topics in **✍️ Generate Articles** to create content
""")
