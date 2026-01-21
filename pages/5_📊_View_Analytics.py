"""
View Analytics Page
System statistics and monitoring dashboard
"""

import streamlit as st
from database import Database
import pandas as pd
import os
from datetime import datetime
from utils.auth import check_password

st.set_page_config(page_title="View Analytics", page_icon="📊", layout="wide")

# Authentication check
if not check_password():
    st.stop()

st.title("📊 System Analytics")
st.markdown("Monitor system performance and content statistics")

st.markdown("---")

# ============================================================================
# KEY METRICS
# ============================================================================

st.markdown("### 📈 Key Metrics")

try:
    db = Database()
    stats = db.get_stats()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Articles",
            stats['total_articles'],
            help="Total articles fetched from legal sources"
        )

    with col2:
        st.metric(
            "Total Topics",
            stats['total_topics'],
            help="Unique legal topics identified"
        )

    with col3:
        avg_articles_per_topic = 0
        if stats['total_topics'] > 0:
            avg_articles_per_topic = round(stats['total_links'] / stats['total_topics'], 1)

        st.metric(
            "Avg Articles/Topic",
            avg_articles_per_topic,
            help="Average source articles per topic"
        )

    with col4:
        try:
            output_dir = 'output/generated_articles'
            if os.path.exists(output_dir):
                generated_count = len([f for f in os.listdir(output_dir) if f.endswith('.md')])
            else:
                generated_count = 0

            st.metric(
                "Generated Articles",
                generated_count,
                help="AI-generated comprehensive articles"
            )
        except:
            st.metric("Generated Articles", 0)

    db.close()

except Exception as e:
    st.error(f"Error loading metrics: {e}")

st.markdown("---")

# ============================================================================
# TOP TOPICS BY ARTICLE COUNT
# ============================================================================

st.markdown("### 🏆 Top 10 Topics by Coverage")

try:
    db = Database()
    all_topics = db.get_topics_with_metadata()

    if all_topics:
        # Sort by article count
        sorted_topics = sorted(all_topics, key=lambda x: x.get('article_count', 0), reverse=True)[:10]

        # Create dataframe
        df_data = []
        for topic in sorted_topics:
            df_data.append({
                'Topic Name': topic['topic_name'],
                'Category': topic.get('category', 'N/A'),
                'Article Count': topic.get('article_count', 0),
                'SMB Score': topic.get('smb_relevance_score', 0),
                'Generated': '✅' if db.is_topic_generated(topic['id']) else '⚠️'
            })

        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

    else:
        st.info("No topics found. Process articles first on the **⚙️ Process Topics** page.")

    db.close()

except Exception as e:
    st.error(f"Error loading top topics: {e}")

st.markdown("---")

# ============================================================================
# TOPIC DISTRIBUTION BY CATEGORY
# ============================================================================

st.markdown("### 📊 Topic Distribution by Category")

try:
    db = Database()
    parent_topics = db.get_parent_topics()

    if parent_topics:
        # Count subtopics per parent
        category_data = []
        for parent in parent_topics:
            subtopics = db.get_subtopics_for_parent(parent['id'])
            category_data.append({
                'Category': parent['topic_name'],
                'Subtopics': len(subtopics),
                'Total Articles': parent.get('article_count', 0)
            })

        df_cat = pd.DataFrame(category_data)
        st.dataframe(df_cat, use_container_width=True, hide_index=True)

        # Simple bar chart
        if len(category_data) > 0:
            st.bar_chart(df_cat.set_index('Category')['Subtopics'])

    else:
        st.info("No parent categories found. Process articles first.")

    db.close()

except Exception as e:
    st.error(f"Error loading category distribution: {e}")

st.markdown("---")

# ============================================================================
# PROCESSING STATUS
# ============================================================================

st.markdown("### ⚙️ Processing Status")

try:
    db = Database()
    stats = db.get_stats()

    total_articles = stats['total_articles']
    processed_articles = total_articles - stats['unprocessed_articles']

    if total_articles > 0:
        processing_rate = (processed_articles / total_articles) * 100

        col_proc1, col_proc2 = st.columns(2)

        with col_proc1:
            st.metric("Processed Articles", processed_articles)
            st.progress(processing_rate / 100)
            st.caption(f"{processing_rate:.1f}% of articles processed")

        with col_proc2:
            st.metric("Unprocessed Articles", stats['unprocessed_articles'])

            if stats['unprocessed_articles'] > 0:
                st.warning(f"⚠️ {stats['unprocessed_articles']} articles need processing")
            else:
                st.success("✅ All articles processed!")

    else:
        st.info("No articles in database yet. Start by fetching articles!")

    db.close()

except Exception as e:
    st.error(f"Error loading processing status: {e}")

st.markdown("---")

# ============================================================================
# GENERATION STATISTICS
# ============================================================================

st.markdown("### ✍️ Generation Statistics")

try:
    db = Database()

    # Count generated vs ungenerated topics
    all_subtopics = [t for t in db.get_topics_with_metadata() if t.get('is_parent', 0) == 0]
    total_subtopics = len(all_subtopics)

    generated_topic_ids = db.get_generated_topics()
    generated_count = len(generated_topic_ids)
    ungenerated_count = total_subtopics - generated_count

    col_gen1, col_gen2, col_gen3 = st.columns(3)

    with col_gen1:
        st.metric("Total Subtopics", total_subtopics)

    with col_gen2:
        st.metric("Generated", generated_count)

    with col_gen3:
        st.metric("Not Generated", ungenerated_count)

    # Generation progress
    if total_subtopics > 0:
        gen_rate = (generated_count / total_subtopics) * 100
        st.progress(gen_rate / 100)
        st.caption(f"{gen_rate:.1f}% of subtopics have been generated")
    else:
        st.info("No subtopics found yet.")

    db.close()

except Exception as e:
    st.error(f"Error loading generation statistics: {e}")

st.markdown("---")

# ============================================================================
# GENERATED ARTICLES OVERVIEW
# ============================================================================

st.markdown("### 📚 Generated Articles Overview")

try:
    output_dir = 'output/generated_articles'

    if os.path.exists(output_dir):
        files = [f for f in os.listdir(output_dir) if f.endswith('.md')]

        if files:
            st.success(f"**{len(files)}** generated articles in output directory")

            # Calculate total word count
            total_words = 0
            total_size = 0

            for filename in files:
                filepath = os.path.join(output_dir, filename)
                with open(filepath, 'r') as f:
                    content = f.read()
                    total_words += len(content.split())
                    total_size += os.path.getsize(filepath)

            col_art1, col_art2, col_art3 = st.columns(3)

            with col_art1:
                st.metric("Total Articles", len(files))

            with col_art2:
                st.metric("Total Words", f"{total_words:,}")

            with col_art3:
                st.metric("Total Size", f"{total_size / 1024:.1f} KB")

            # Average word count
            if len(files) > 0:
                avg_words = total_words / len(files)
                st.info(f"📊 **Average article length:** {avg_words:.0f} words")

        else:
            st.info("No generated articles yet. Use **✍️ Generate Articles** to create content.")

    else:
        st.info("Output directory not found. Generate your first article to create it.")

except Exception as e:
    st.error(f"Error loading generated articles overview: {e}")

st.markdown("---")

# ============================================================================
# HIGH-VALUE TOPICS (UNGENERATED)
# ============================================================================

st.markdown("### 💎 High-Value Topics (Not Yet Generated)")

st.markdown("These topics have high SMB relevance and good article coverage but haven't been generated yet.")

try:
    db = Database()

    # Get high-value ungenerated topics
    ungenerated = db.get_ungenerated_subtopics(min_score=8, min_articles=3)

    if ungenerated:
        st.success(f"Found **{len(ungenerated)}** high-value topics ready for generation")

        # Display top 10
        top_ungenerated = ungenerated[:10]

        df_data = []
        for topic in top_ungenerated:
            df_data.append({
                'ID': topic['id'],
                'Topic Name': topic['topic_name'],
                'SMB Score': topic.get('smb_relevance_score', 0),
                'Article Count': topic.get('article_count', 0)
            })

        df_ungen = pd.DataFrame(df_data)
        st.dataframe(df_ungen, use_container_width=True, hide_index=True)

        st.info("💡 **Tip:** Use **✍️ Generate Articles** → **Auto-Generate Top Topics** to batch generate these.")

    else:
        st.success("✅ All high-value topics have been generated!")

    db.close()

except Exception as e:
    st.error(f"Error loading high-value topics: {e}")

st.markdown("---")

# ============================================================================
# SYSTEM INFO
# ============================================================================

with st.expander("🖥️ System Information"):
    st.markdown("""
    **Database Location:**
    - Local: `data/pipeline.db`
    - Railway: `/data/pipeline.db` (persistent volume)

    **AI Models:**
    - Topic Extraction: Gemini 2.5 Flash (~$0.001/article)
    - Article Generation: Claude Sonnet 4.5 (~$0.12/article) or Haiku (~$0.01/article)

    **Data Sources:**
    - Slaw
    - McCarthy Tétrault
    - Monkhouse Law
    - CanLII

    **Refresh Rate:**
    - Manual refresh required (rerun page to update stats)
    """)

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 0.8em;'>
    <p>Analytics Dashboard | Canadian Legal News Pipeline</p>
    <p>Last refreshed: {}</p>
</div>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), unsafe_allow_html=True)
