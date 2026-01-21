"""
Process Topics Page
Extracts topics from unprocessed articles using Gemini AI
"""

import streamlit as st
from database import Database
from utils.subprocess_runner import run_pipeline_script_streaming, parse_compile_output
from utils.auth import check_password

st.set_page_config(page_title="Process Topics", page_icon="⚙️", layout="wide")

# Authentication check
if not check_password():
    st.stop()

st.title("⚙️ Process Topics")
st.markdown("Extract topics from articles using AI-powered analysis")

st.markdown("---")

# ============================================================================
# CURRENT STATUS
# ============================================================================

st.markdown("### 📊 Current Status")

try:
    db = Database()
    stats = db.get_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Articles", stats['total_articles'])

    with col2:
        st.metric(
            "Unprocessed Articles",
            stats['unprocessed_articles'],
            help="Articles that haven't been analyzed for topics yet"
        )

    with col3:
        st.metric("Total Topics", stats['total_topics'])

    with col4:
        st.metric("Article-Topic Links", stats['total_links'])

    db.close()

except Exception as e:
    st.error(f"Error loading stats: {e}")

st.markdown("---")

# ============================================================================
# HOW IT WORKS
# ============================================================================

st.markdown("### 🤖 How Topic Extraction Works")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("""
    **3-Level Hierarchical Topic Structure:**

    1. **Parent Topic** (Category)
       - Example: "Employment Law"
       - Broad legal category

    2. **Subtopic** (Specific Topic)
       - Example: "Wrongful Dismissal"
       - Specific legal issue within category

    3. **Article Tag** (Specific Aspect)
       - Example: "Termination during pregnancy leave"
       - Specific angle discussed in article
    """)

with col_right:
    st.markdown("""
    **AI Processing:**

    - Uses **Gemini 2.5 Flash** AI model
    - Analyzes article content for legal topics
    - Normalizes topic names across sources
    - Assigns SMB relevance score (0-10)
    - Links articles to identified topics

    **SMB Relevance Score:**
    - 8-10: Highly relevant to SMBs
    - 5-7: Moderately relevant
    - 0-4: Low relevance (large enterprise focus)
    """)

st.markdown("---")

# ============================================================================
# COST AND TIME ESTIMATION
# ============================================================================

try:
    db = Database()
    stats = db.get_stats()
    unprocessed = stats['unprocessed_articles']

    if unprocessed > 0:
        st.markdown("### 💰 Cost & Time Estimation")

        # Calculate estimates
        cost_per_article = 0.001  # Approximate cost for Gemini 2.5 Flash
        time_per_article = 3  # Seconds per article (approximate)

        total_cost = unprocessed * cost_per_article
        total_time = unprocessed * time_per_article

        col_warn, col_cost, col_time = st.columns(3)

        with col_warn:
            st.warning(f"⚠️ **{unprocessed}** articles need processing")

        with col_cost:
            st.info(f"💰 **Estimated cost:** ${total_cost:.2f}")

        with col_time:
            st.info(f"⏱️ **Estimated time:** ~{total_time} seconds")

        st.markdown("---")

    db.close()

except Exception as e:
    st.error(f"Error calculating estimates: {e}")

# ============================================================================
# PROCESS OPERATION
# ============================================================================

st.markdown("### 🚀 Process Articles")

try:
    db = Database()
    stats = db.get_stats()
    unprocessed = stats['unprocessed_articles']
    db.close()

    if unprocessed == 0:
        st.success("✅ All articles have been processed!")
        st.info("Fetch new articles on the **📥 Fetch Articles** page to process more.")

    else:
        st.markdown(f"""
        Click the button below to process **{unprocessed}** unprocessed articles.

        **What happens during processing:**
        1. Each article is analyzed by Gemini AI
        2. Topics are extracted and normalized
        3. SMB relevance scores are assigned
        4. Articles are linked to topics in database
        5. Articles are marked as processed

        **Note:** This process uses the Gemini AI API and will incur costs (~$0.001 per article).
        """)

        if st.button("⚙️ Process All Unprocessed Articles", type="primary", use_container_width=True):
            st.markdown(f"### 🔄 Processing {unprocessed} Articles")
            st.markdown("Watch the live progress below. This may take several minutes.")
            st.markdown("---")

            # Run compile.py with real-time streaming output
            success, stdout, stderr = run_pipeline_script_streaming("compile.py", timeout=1800)

            if success:
                st.markdown("---")

                # Parse output to show statistics
                compile_stats = parse_compile_output(stdout)

                if compile_stats['processed_count'] > 0 or compile_stats['topics_created'] > 0:
                    st.markdown("### 📊 Processing Results")
                    col_processed, col_topics = st.columns(2)

                    with col_processed:
                        st.metric(
                            "Articles Processed",
                            compile_stats['processed_count'],
                            help="Articles analyzed for topics"
                        )

                    with col_topics:
                        st.metric(
                            "Topics Created",
                            compile_stats['topics_created'],
                            help="New unique topics added to database"
                        )

                st.info("📊 Database stats updated! Refresh the page to see the latest numbers.")
                st.balloons()

except Exception as e:
    st.error(f"Error: {e}")

st.markdown("---")

# ============================================================================
# TROUBLESHOOTING
# ============================================================================

with st.expander("🔧 Troubleshooting"):
    st.markdown("""
    **Common Issues:**

    1. **API quota exceeded** - Gemini API has rate limits. Wait a few minutes and try again.

    2. **Processing timeout** - For large batches (100+ articles), the process may take 5-10 minutes.

    3. **API key errors** - Ensure GEMINI_API_KEY is set in environment variables.

    4. **Duplicate topic warnings** - This is normal - the system normalizes similar topics to prevent duplicates.

    **What to do if processing fails:**
    - Check the error log above for specific issues
    - Verify GEMINI_API_KEY environment variable is set
    - Try running compile.py manually: `python compile.py`
    - Check Gemini API quotas in Google Cloud Console
    """)

# ============================================================================
# NEXT STEPS
# ============================================================================

st.markdown("### ➡️ Next Steps")

st.info("""
After processing topics:
1. Go to **📁 Browse Topics** to explore the hierarchical topic structure
2. Filter topics by SMB relevance score
3. Select high-relevance topics for article generation
4. Use **✍️ Generate Articles** to create comprehensive content
""")
