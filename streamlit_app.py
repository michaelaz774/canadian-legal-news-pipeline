"""
Canadian Legal News Pipeline - Streamlit Web Interface
Main entry point and home dashboard

This is a Streamlit multi-page application that provides a web interface
for the Canadian Legal News Pipeline system.
"""

import streamlit as st
from database import Database
from utils.auth import check_password
import os
from datetime import datetime

# ============================================================================
# PAGE CONFIG - MUST BE FIRST STREAMLIT COMMAND
# ============================================================================
st.set_page_config(
    page_title="Legal News Pipeline",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': "Canadian Legal News Pipeline - Automated content generation for SMBs"
    }
)

# ============================================================================
# AUTHENTICATION
# ============================================================================
if not check_password():
    st.stop()

# ============================================================================
# SIDEBAR - DATABASE STATS
# ============================================================================
st.sidebar.title("⚖️ Legal News Pipeline")
st.sidebar.markdown("---")

# Get database statistics
try:
    db = Database()
    stats = db.get_stats()

    st.sidebar.header("📊 Database Stats")
    st.sidebar.metric("Total Articles", stats['total_articles'])
    st.sidebar.metric("Total Topics", stats['total_topics'])
    st.sidebar.metric("Article-Topic Links", stats['total_links'])
    st.sidebar.metric("Unprocessed Articles", stats['unprocessed_articles'])

    # Check for generated articles
    try:
        output_dir = 'output/generated_articles'
        if os.path.exists(output_dir):
            generated_files = [f for f in os.listdir(output_dir) if f.endswith('.md')]
            st.sidebar.metric("Generated Articles", len(generated_files))
        else:
            st.sidebar.metric("Generated Articles", 0)
    except:
        st.sidebar.metric("Generated Articles", 0)

    db.close()

except Exception as e:
    st.sidebar.error(f"Error loading stats: {e}")

st.sidebar.markdown("---")
st.sidebar.info("Navigate using the pages in the sidebar to access different features.")

# ============================================================================
# MAIN DASHBOARD
# ============================================================================

st.title("⚖️ Canadian Legal News Pipeline")
st.markdown("### Automated Legal Content Generation for Canadian SMBs")

st.markdown("---")

# Overview section
st.markdown("""
This system automatically:
1. **Fetches** articles from Canadian legal sources
2. **Extracts** and organizes topics using AI (Gemini 2.5 Flash)
3. **Generates** comprehensive articles using AI (Claude Sonnet 4.5)

Use the navigation menu on the left to access different features.
""")

# ============================================================================
# KEY METRICS DASHBOARD
# ============================================================================

st.markdown("### 📈 System Overview")

col1, col2, col3, col4 = st.columns(4)

try:
    db = Database()
    stats = db.get_stats()

    with col1:
        st.metric(
            label="Articles in Database",
            value=stats['total_articles'],
            delta=None,
            help="Total articles fetched from legal news sources"
        )

    with col2:
        st.metric(
            label="Topics Extracted",
            value=stats['total_topics'],
            delta=None,
            help="Unique legal topics identified by AI"
        )

    with col3:
        avg_articles_per_topic = 0
        if stats['total_topics'] > 0:
            avg_articles_per_topic = round(stats['total_links'] / stats['total_topics'], 1)

        st.metric(
            label="Avg Articles/Topic",
            value=avg_articles_per_topic,
            delta=None,
            help="Average number of source articles per topic"
        )

    with col4:
        try:
            output_dir = 'output/generated_articles'
            if os.path.exists(output_dir):
                generated_count = len([f for f in os.listdir(output_dir) if f.endswith('.md')])
            else:
                generated_count = 0

            st.metric(
                label="Generated Articles",
                value=generated_count,
                delta=None,
                help="Number of AI-generated articles"
            )
        except:
            st.metric(label="Generated Articles", value=0)

    db.close()

except Exception as e:
    st.error(f"Error loading metrics: {e}")

st.markdown("---")

# ============================================================================
# QUICK START GUIDE
# ============================================================================

st.markdown("### 🚀 Quick Start Guide")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("""
    #### Daily Workflow

    1. **📥 Fetch Articles** - Scrape new articles from legal sources
    2. **⚙️ Process Topics** - Extract topics using AI
    3. **📁 Browse Topics** - Explore the topic hierarchy
    4. **✍️ Generate Articles** - Create comprehensive articles
    5. **📊 View Analytics** - Monitor system statistics
    """)

with col_right:
    st.markdown("""
    #### System Status

    **Data Sources:**
    - Slaw (Canadian legal blog)
    - McCarthy Tétrault (law firm insights)
    - Monkhouse Law (employment law)
    - CanLII (case law database)

    **AI Models:**
    - Gemini 2.5 Flash (topic extraction)
    - Claude Sonnet 4.5 (article generation)
    """)

st.markdown("---")

# ============================================================================
# RECENT ACTIVITY
# ============================================================================

st.markdown("### 📋 Recent Activity")

try:
    db = Database()

    # Get recent topics with metadata
    topics = db.get_topics_with_metadata()

    if topics:
        # Show most recent 5 topics
        recent_topics = sorted(topics, key=lambda x: x['created_date'], reverse=True)[:5]

        st.markdown("**Recently Extracted Topics:**")

        for topic in recent_topics:
            col_topic, col_score, col_articles = st.columns([3, 1, 1])

            with col_topic:
                st.markdown(f"**{topic['topic_name']}**")
                if topic.get('category'):
                    st.caption(f"Category: {topic['category']}")

            with col_score:
                score = topic.get('smb_relevance_score', 0)
                if score >= 8:
                    st.success(f"SMB Score: {score}/10")
                elif score >= 5:
                    st.info(f"SMB Score: {score}/10")
                else:
                    st.warning(f"SMB Score: {score}/10")

            with col_articles:
                article_count = topic.get('article_count', 0)
                st.metric("Articles", article_count)

            st.markdown("---")

    else:
        st.info("No topics extracted yet. Start by fetching articles and processing them!")

    db.close()

except Exception as e:
    st.error(f"Error loading recent activity: {e}")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    <p>Canadian Legal News Pipeline | Built with Streamlit, Gemini AI, and Claude AI</p>
    <p>For Canadian SMB legal content generation</p>
</div>
""", unsafe_allow_html=True)
