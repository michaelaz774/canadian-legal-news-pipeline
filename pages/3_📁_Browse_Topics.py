"""
Browse Topics Page
Interactive topic browser with hierarchy visualization and filtering
"""

import streamlit as st
from database import Database
import pandas as pd
from utils.auth import check_password

st.set_page_config(page_title="Browse Topics", page_icon="📁", layout="wide")

# Authentication check
if not check_password():
    st.stop()

st.title("📁 Browse Topics")
st.markdown("Explore the hierarchical topic structure extracted from legal articles")

st.markdown("---")

# ============================================================================
# TABS FOR DIFFERENT VIEWS
# ============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "🌳 Hierarchy View",
    "🔍 Search Topics",
    "🎯 Filter Topics",
    "📄 Topic Details"
])

# ============================================================================
# TAB 1: HIERARCHY VIEW
# ============================================================================

with tab1:
    st.markdown("### 🌳 Topic Hierarchy")
    st.markdown("Topics organized by parent category with subtopics")

    try:
        db = Database()

        # Get parent topics
        parent_topics = db.get_parent_topics()

        if not parent_topics:
            st.info("No parent topics found. Process some articles first on the **⚙️ Process Topics** page.")
        else:
            st.success(f"Found **{len(parent_topics)}** parent categories")

            # Display each parent topic with its subtopics
            for parent in parent_topics:
                parent_article_count = parent.get('article_count', 0)
                parent_score = parent.get('smb_relevance_score', 0)

                # Create expander for each parent topic
                with st.expander(
                    f"📁 **{parent['topic_name']}** | SMB Score: {parent_score}/10 | {parent_article_count} articles",
                    expanded=False
                ):
                    # Get subtopics for this parent
                    subtopics = db.get_subtopics_for_parent(parent['id'])

                    if subtopics:
                        st.markdown(f"**{len(subtopics)}** subtopics:")

                        # Display subtopics with nested article view
                        for subtopic in subtopics:
                            subtopic_id = subtopic['id']
                            subtopic_name = subtopic['topic_name']
                            subtopic_score = subtopic.get('smb_relevance_score', 0)
                            subtopic_articles = subtopic.get('article_count', 0)

                            # Check if topic has been generated
                            is_generated = db.is_topic_generated(subtopic_id)
                            status_icon = "✅" if is_generated else "⚠️"

                            # Color code by SMB relevance
                            if subtopic_score >= 8:
                                score_color = "🟢"
                            elif subtopic_score >= 5:
                                score_color = "🟡"
                            else:
                                score_color = "🔴"

                            # Create nested expander for each subtopic to show its articles
                            with st.expander(
                                f"{status_icon} **{subtopic_name}** (ID: {subtopic_id}) | {score_color} {subtopic_score}/10 | 📄 {subtopic_articles} articles",
                                expanded=False
                            ):
                                # Get articles for this subtopic
                                articles = db.get_articles_for_topic(subtopic_id)

                                if articles:
                                    st.markdown(f"**{len(articles)} source articles:**")

                                    for idx, article in enumerate(articles, 1):
                                        st.markdown(f"**{idx}. {article['title']}**")

                                        col_art1, col_art2 = st.columns(2)

                                        with col_art1:
                                            st.markdown(f"📰 **Source:** {article['source']}")
                                            if article.get('published_date'):
                                                st.markdown(f"📅 **Published:** {article['published_date']}")

                                        with col_art2:
                                            st.markdown(f"🔗 **URL:** [{article['url'][:50]}...]({article['url']})")
                                            if article.get('fetched_date'):
                                                st.markdown(f"📥 **Fetched:** {article['fetched_date'][:10]}")

                                        if article.get('summary'):
                                            with st.expander("📄 Summary"):
                                                st.markdown(article['summary'])

                                        st.markdown("---")
                                else:
                                    st.info("No articles linked to this subtopic yet.")

                    else:
                        st.info("No subtopics found for this parent category.")

        db.close()

    except Exception as e:
        st.error(f"Error loading hierarchy: {e}")

# ============================================================================
# TAB 2: SEARCH TOPICS
# ============================================================================

with tab2:
    st.markdown("### 🔍 Search Topics")

    search_query = st.text_input(
        "Enter search terms",
        placeholder="e.g., employment, contract, Smith",
        help="Search topic names and categories"
    )

    if search_query:
        try:
            db = Database()
            all_topics = db.get_topics_with_metadata()

            # Filter topics by search query (case-insensitive)
            matching_topics = [
                topic for topic in all_topics
                if search_query.lower() in topic['topic_name'].lower()
                or (topic.get('category') and search_query.lower() in topic['category'].lower())
                or (topic.get('key_entity') and search_query.lower() in topic['key_entity'].lower())
            ]

            if matching_topics:
                st.success(f"Found **{len(matching_topics)}** matching topics")

                # Display as dataframe
                df_data = []
                for topic in matching_topics:
                    df_data.append({
                        'ID': topic['id'],
                        'Topic Name': topic['topic_name'],
                        'Category': topic.get('category', ''),
                        'SMB Score': topic.get('smb_relevance_score', 0),
                        'Articles': topic.get('article_count', 0),
                        'Generated': '✅' if db.is_topic_generated(topic['id']) else '⚠️'
                    })

                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

            else:
                st.warning(f"No topics found matching '{search_query}'")

            db.close()

        except Exception as e:
            st.error(f"Error searching topics: {e}")

    else:
        st.info("Enter a search term above to find topics")

# ============================================================================
# TAB 3: FILTER TOPICS
# ============================================================================

with tab3:
    st.markdown("### 🎯 Filter Topics")

    col_filter1, col_filter2 = st.columns(2)

    with col_filter1:
        min_score = st.slider(
            "Minimum SMB Relevance Score",
            min_value=0,
            max_value=10,
            value=5,
            help="Filter topics by SMB relevance score (0-10)"
        )

    with col_filter2:
        min_articles = st.slider(
            "Minimum Article Count",
            min_value=1,
            max_value=20,
            value=3,
            help="Filter topics by number of source articles"
        )

    show_generated = st.checkbox("Show only ungenerated topics", value=False)

    if st.button("Apply Filters", type="primary"):
        try:
            db = Database()
            all_topics = db.get_topics_with_metadata()

            # Apply filters
            filtered_topics = [
                topic for topic in all_topics
                if topic.get('smb_relevance_score', 0) >= min_score
                and topic.get('article_count', 0) >= min_articles
                and topic.get('is_parent', 0) == 0  # Only subtopics
            ]

            if show_generated:
                filtered_topics = [
                    topic for topic in filtered_topics
                    if not db.is_topic_generated(topic['id'])
                ]

            if filtered_topics:
                st.success(f"Found **{len(filtered_topics)}** topics matching filters")

                # Sort by article count (descending)
                filtered_topics = sorted(
                    filtered_topics,
                    key=lambda x: x.get('article_count', 0),
                    reverse=True
                )

                # Display as dataframe
                df_data = []
                for topic in filtered_topics:
                    df_data.append({
                        'ID': topic['id'],
                        'Topic Name': topic['topic_name'],
                        'Category': topic.get('category', ''),
                        'SMB Score': topic.get('smb_relevance_score', 0),
                        'Articles': topic.get('article_count', 0),
                        'Generated': '✅' if db.is_topic_generated(topic['id']) else '⚠️'
                    })

                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Option to export IDs
                topic_ids = [topic['id'] for topic in filtered_topics]
                st.markdown(f"**Topic IDs:** {', '.join(map(str, topic_ids))}")

                if st.button("📋 Copy IDs to Clipboard"):
                    ids_str = ','.join(map(str, topic_ids))
                    st.code(ids_str)
                    st.info("IDs displayed above - use for batch generation")

            else:
                st.warning("No topics found matching the selected filters")

            db.close()

        except Exception as e:
            st.error(f"Error filtering topics: {e}")

# ============================================================================
# TAB 4: TOPIC DETAILS
# ============================================================================

with tab4:
    st.markdown("### 📄 Topic Details")

    topic_id = st.number_input(
        "Enter Topic ID",
        min_value=1,
        step=1,
        help="Enter a topic ID to view its details and source articles"
    )

    if st.button("View Topic", type="primary"):
        try:
            db = Database()

            # Get topic information
            topic = db.get_topic_by_id(topic_id)

            if topic:
                st.success(f"Topic ID {topic_id} found!")

                # Display topic metadata
                col_meta1, col_meta2, col_meta3 = st.columns(3)

                with col_meta1:
                    st.metric("Topic Name", "")
                    st.markdown(f"**{topic['topic_name']}**")

                with col_meta2:
                    st.metric("SMB Relevance Score", f"{topic.get('smb_relevance_score', 0)}/10")

                with col_meta3:
                    st.metric("Article Count", topic.get('article_count', 0))

                if topic.get('category'):
                    st.info(f"**Category:** {topic['category']}")

                if topic.get('key_entity'):
                    st.info(f"**Key Entity:** {topic['key_entity']}")

                # Check if generated
                if db.is_topic_generated(topic_id):
                    st.success("✅ This topic has been generated")
                    gen_info = db.get_generation_info(topic_id)
                    if gen_info:
                        st.markdown(f"**Generated:** {gen_info.get('generated_date', 'N/A')}")
                        st.markdown(f"**Model Used:** {gen_info.get('model_used', 'N/A')}")
                        st.markdown(f"**Word Count:** {gen_info.get('word_count', 'N/A')}")
                else:
                    st.warning("⚠️ This topic has not been generated yet")

                st.markdown("---")

                # Get articles for this topic
                articles = db.get_articles_for_topic(topic_id)

                if articles:
                    st.markdown(f"### 📰 Source Articles ({len(articles)})")

                    for article in articles:
                        with st.expander(f"{article['title']} ({article['source']})"):
                            col_art1, col_art2 = st.columns(2)

                            with col_art1:
                                st.markdown(f"**Source:** {article['source']}")
                                st.markdown(f"**Published:** {article.get('published_date', 'N/A')}")

                            with col_art2:
                                st.markdown(f"**Fetched:** {article.get('fetched_date', 'N/A')}")
                                st.markdown(f"**URL:** [{article['url']}]({article['url']})")

                            if article.get('summary'):
                                st.markdown("**Summary:**")
                                st.markdown(article['summary'])

                else:
                    st.warning("No articles found for this topic")

            else:
                st.error(f"Topic ID {topic_id} not found")

            db.close()

        except Exception as e:
            st.error(f"Error loading topic details: {e}")

st.markdown("---")

# ============================================================================
# FOOTER
# ============================================================================

st.info("""
**Next Steps:**
- Use **✍️ Generate Articles** to create content for specific topics
- High SMB scores (8-10) are best for SMB-focused content
- Topics with 3+ articles provide more comprehensive coverage
""")
