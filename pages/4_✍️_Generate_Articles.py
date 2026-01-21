"""
Generate Articles Page
AI-powered article generation with multiple generation modes
"""

import streamlit as st
from database import Database
from utils.subprocess_runner import run_pipeline_script_streaming, parse_generate_output
from utils.auth import check_password
import os

st.set_page_config(page_title="Generate Articles", page_icon="✍️", layout="wide")

# Authentication check
if not check_password():
    st.stop()

st.title("✍️ Generate Articles")
st.markdown("Create comprehensive articles using AI synthesis")

st.markdown("---")

# ============================================================================
# TABS FOR DIFFERENT GENERATION MODES
# ============================================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 Generate by Subtopic ID",
    "☑️ Select Multiple Subtopics",
    "📄 Select Specific Articles",
    "🤖 Auto-Generate Top Topics",
    "📚 View Generated Articles"
])

# ============================================================================
# TAB 1: GENERATE BY SUBTOPIC ID
# ============================================================================

with tab1:
    st.markdown("### 🎯 Generate by Subtopic ID")
    st.markdown("Generate an article for a specific subtopic")

    # Topic ID input
    topic_id = st.number_input(
        "Enter Subtopic ID",
        min_value=1,
        value=None,
        step=1,
        format="%d",
        help="Enter the ID of a subtopic to generate an article"
    )

    # Model selection
    col_model, col_cost = st.columns(2)

    with col_model:
        model = st.radio(
            "Select AI Model",
            ["sonnet", "haiku"],
            horizontal=True,
            help="Sonnet: Higher quality, more expensive | Haiku: Faster, cheaper"
        )

    with col_cost:
        cost_per_article = 0.12 if model == "sonnet" else 0.01
        st.metric("Estimated Cost", f"${cost_per_article:.2f}")

    # Show topic info if ID is valid
    if topic_id:
        try:
            db = Database()
            topic = db.get_topic_by_id(topic_id)

            if topic:
                st.success(f"Topic found: **{topic['topic_name']}**")

                col_info1, col_info2, col_info3 = st.columns(3)

                with col_info1:
                    st.metric("SMB Score", f"{topic.get('smb_relevance_score', 0)}/10")

                with col_info2:
                    article_count = topic.get('article_count', 0)
                    st.metric("Source Articles", article_count)

                with col_info3:
                    is_generated = db.is_topic_generated(topic_id)
                    status = "✅ Already Generated" if is_generated else "⚠️ Not Generated"
                    st.info(status)

                if topic.get('category'):
                    st.markdown(f"**Category:** {topic['category']}")

            else:
                st.warning(f"Topic ID {topic_id} not found. Use **📁 Browse Topics** to find valid IDs.")

            db.close()

        except Exception as e:
            st.error(f"Error loading topic: {e}")

    st.markdown("---")

    # Generate button
    if st.button("✍️ Generate Article", type="primary", use_container_width=True):
        if not topic_id or topic_id < 1:
            st.error("Please enter a valid topic ID (must be a positive integer)")
        else:
            with st.spinner(f"Generating article using Claude {model.capitalize()}... This may take 1-2 minutes."):
                # Build command
                args = ['--topic', str(int(topic_id)), '--model', model]

                # Debug logging
                st.info(f"Running generate.py with arguments: {' '.join(args)}")

                # Run generate.py
                success, stdout, stderr = run_pipeline_script_streaming("generate.py", args=args, timeout=600)

                if success:
                    st.success("✅ Article generated successfully!")

                    # Parse output
                    gen_stats = parse_generate_output(stdout)

                    if gen_stats['word_count'] > 0:
                        col_wc, col_cost_actual = st.columns(2)

                        with col_wc:
                            st.metric("Word Count", gen_stats['word_count'])

                        with col_cost_actual:
                            if gen_stats['cost'] > 0:
                                st.metric("Actual Cost", f"${gen_stats['cost']:.2f}")

                    # Display output
                    display_script_output(stdout, stderr, show_stdout=True)

                    st.balloons()

                    # Show download section
                    if gen_stats['output_file']:
                        st.markdown("---")
                        st.markdown("### 📥 Download Article")

                        # Try to find the generated file
                        output_dir = 'output/generated_articles'
                        if os.path.exists(output_dir):
                            files = [f for f in os.listdir(output_dir) if f.endswith('.md')]
                            if files:
                                # Find most recent file (likely the one just generated)
                                latest_file = max([os.path.join(output_dir, f) for f in files], key=os.path.getctime)

                                with open(latest_file, 'r') as f:
                                    content = f.read()

                                st.download_button(
                                    label="📥 Download Article (Markdown)",
                                    data=content,
                                    file_name=os.path.basename(latest_file),
                                    mime="text/markdown"
                                )

                                # Show preview
                                with st.expander("👁️ Preview Article"):
                                    st.markdown(content)

                else:
                    st.error("❌ Generation failed!")
                    st.markdown("**Error details:**")
                    display_script_output(stdout, stderr)

# ============================================================================
# TAB 2: SELECT MULTIPLE SUBTOPICS
# ============================================================================

with tab2:
    st.markdown("### ☑️ Select Multiple Subtopics")
    st.markdown("Browse and select specific subtopics to generate")

    # Filter controls
    col_filter1, col_filter2, col_filter3 = st.columns(3)

    with col_filter1:
        # Get all parent topics for filtering
        db_temp = Database()
        parent_topics = db_temp.get_parent_topics()
        parent_options = ["All Categories"] + [p['topic_name'] for p in parent_topics]
        selected_parent = st.selectbox("Filter by Parent Category", parent_options)

    with col_filter2:
        min_score_select = st.slider(
            "Minimum SMB Score",
            min_value=0,
            max_value=10,
            value=5,
            key="select_min_score"
        )

    with col_filter3:
        min_articles_select = st.slider(
            "Minimum Articles",
            min_value=1,
            max_value=10,
            value=2,
            key="select_min_articles"
        )

    show_only_ungenerated = st.checkbox("Show only ungenerated topics", value=True)

    st.markdown("---")

    # Get all subtopics based on filters
    try:
        db = Database()
        all_topics = db.get_topics_with_metadata()

        # Filter subtopics
        filtered_subtopics = [
            t for t in all_topics
            if t.get('is_parent', 0) == 0  # Only subtopics
            and t.get('smb_relevance_score', 0) >= min_score_select
            and t.get('article_count', 0) >= min_articles_select
        ]

        # Filter by parent if selected
        if selected_parent != "All Categories":
            selected_parent_id = next((p['id'] for p in parent_topics if p['topic_name'] == selected_parent), None)
            if selected_parent_id:
                filtered_subtopics = [
                    t for t in filtered_subtopics
                    if t.get('parent_topic_id') == selected_parent_id
                ]

        # Filter by generation status
        if show_only_ungenerated:
            filtered_subtopics = [
                t for t in filtered_subtopics
                if not db.is_topic_generated(t['id'])
            ]

        if filtered_subtopics:
            st.success(f"Found **{len(filtered_subtopics)}** subtopics matching filters")

            # Model selection
            model_multi = st.radio(
                "Select AI Model",
                ["sonnet", "haiku"],
                horizontal=True,
                key="model_multi"
            )

            st.markdown("---")
            st.markdown("### Select Subtopics to Generate")

            # Create checkboxes for each subtopic
            selected_subtopics = []

            for subtopic in filtered_subtopics:
                col_check, col_info = st.columns([0.5, 9])

                with col_check:
                    is_selected = st.checkbox(
                        "",
                        key=f"select_{subtopic['id']}",
                        label_visibility="collapsed"
                    )

                with col_info:
                    # Show topic info
                    score = subtopic.get('smb_relevance_score', 0)
                    article_count = subtopic.get('article_count', 0)

                    # Color code by SMB score
                    if score >= 8:
                        score_badge = f"🟢 {score}/10"
                    elif score >= 5:
                        score_badge = f"🟡 {score}/10"
                    else:
                        score_badge = f"🔴 {score}/10"

                    st.markdown(f"**{subtopic['topic_name']}** (ID: {subtopic['id']})")
                    st.caption(f"{score_badge} | 📄 {article_count} articles | Category: {subtopic.get('category', 'N/A')}")

                    # Show article preview in expander
                    with st.expander("👁️ View Source Articles"):
                        articles = db.get_articles_for_topic(subtopic['id'])
                        for idx, article in enumerate(articles, 1):
                            st.markdown(f"{idx}. **{article['title']}** ({article['source']})")

                if is_selected:
                    selected_subtopics.append(subtopic)

                st.markdown("---")

            # Show generation summary
            if selected_subtopics:
                st.markdown("---")
                st.markdown("### 📋 Generation Summary")

                col_sum1, col_sum2 = st.columns(2)

                with col_sum1:
                    st.metric("Selected Subtopics", len(selected_subtopics))

                with col_sum2:
                    cost_per = 0.12 if model_multi == "sonnet" else 0.01
                    total_cost = len(selected_subtopics) * cost_per
                    st.metric("Estimated Cost", f"${total_cost:.2f}")

                # Show selected list
                with st.expander("📄 Selected Topics Preview"):
                    for subtopic in selected_subtopics:
                        st.markdown(f"- **{subtopic['topic_name']}** ({subtopic.get('article_count', 0)} articles)")

                # Generate button
                if st.button("🚀 Generate Selected Topics", type="primary", use_container_width=True):
                    st.info(f"Starting generation for {len(selected_subtopics)} selected topics...")

                    success_count = 0
                    fail_count = 0

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for i, subtopic in enumerate(selected_subtopics):
                        topic_id = subtopic['id']
                        topic_name = subtopic['topic_name']

                        status_text.markdown(f"**Generating {i+1}/{len(selected_subtopics)}:** {topic_name}")

                        # Run generation
                        args = ['--topic', str(topic_id), '--model', model_multi]
                        success, stdout, stderr = run_pipeline_script_streaming("generate.py", args=args, timeout=600)

                        if success:
                            success_count += 1
                            st.success(f"✅ Generated: {topic_name}")
                        else:
                            fail_count += 1
                            st.error(f"❌ Failed: {topic_name}")

                        # Update progress
                        progress_bar.progress((i + 1) / len(selected_subtopics))

                    status_text.markdown("### Generation Complete!")
                    st.balloons()

                    col_success, col_fail = st.columns(2)
                    with col_success:
                        st.metric("Successful", success_count)
                    with col_fail:
                        st.metric("Failed", fail_count)

            else:
                st.info("👆 Select one or more subtopics above to generate articles")

        else:
            st.warning("No subtopics match the selected filters. Try adjusting the filter criteria.")

        db.close()

    except Exception as e:
        st.error(f"Error loading subtopics: {e}")

# ============================================================================
# TAB 3: SELECT SPECIFIC ARTICLES
# ============================================================================

with tab3:
    st.markdown("### 📄 Select Specific Articles")
    st.markdown("Pick individual articles to include in your generated content")

    # Step 1: Select a subtopic
    try:
        db = Database()
        all_topics = db.get_topics_with_metadata()

        # Only show subtopics with articles
        subtopics_with_articles = [
            t for t in all_topics
            if t.get('is_parent', 0) == 0 and t.get('article_count', 0) > 0
        ]

        if subtopics_with_articles:
            # Sort by article count (most articles first)
            subtopics_with_articles = sorted(
                subtopics_with_articles,
                key=lambda x: x.get('article_count', 0),
                reverse=True
            )

            # Create dropdown options
            topic_options = {
                f"{t['topic_name']} ({t.get('article_count', 0)} articles)": t['id']
                for t in subtopics_with_articles
            }

            selected_topic_name = st.selectbox(
                "Select Subtopic",
                options=list(topic_options.keys()),
                help="Choose a subtopic to see its source articles"
            )

            selected_topic_id = topic_options[selected_topic_name]

            # Get the selected topic details
            selected_topic = next((t for t in subtopics_with_articles if t['id'] == selected_topic_id), None)

            if selected_topic:
                col_info1, col_info2, col_info3 = st.columns(3)

                with col_info1:
                    st.metric("SMB Score", f"{selected_topic.get('smb_relevance_score', 0)}/10")

                with col_info2:
                    st.metric("Total Articles", selected_topic.get('article_count', 0))

                with col_info3:
                    is_generated = db.is_topic_generated(selected_topic_id)
                    status = "✅ Generated" if is_generated else "⚠️ Not Generated"
                    st.info(status)

                st.markdown("---")

                # Step 2: Get and display articles with checkboxes
                articles = db.get_articles_for_topic(selected_topic_id)

                if articles:
                    st.markdown("### Select Articles to Include")
                    st.markdown("Check the articles you want to use for generation:")

                    # Select all / Deselect all buttons
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("✅ Select All", use_container_width=True):
                            for article in articles:
                                st.session_state[f"check_{article['id']}"] = True
                            st.rerun()
                    with col_btn2:
                        if st.button("❌ Deselect All", use_container_width=True):
                            for article in articles:
                                st.session_state[f"check_{article['id']}"] = False
                            st.rerun()

                    st.markdown("---")

                    # Track selected articles
                    selected_articles = []

                    # Display each article with checkbox
                    for idx, article in enumerate(articles, 1):
                        col_check, col_article = st.columns([0.5, 9.5])

                        with col_check:
                            # Initialize checkbox state if not exists
                            checkbox_key = f"check_{article['id']}"
                            if checkbox_key not in st.session_state:
                                st.session_state[checkbox_key] = True  # Default: all selected

                            # Use checkbox with key only (Streamlit manages the state)
                            is_selected = st.checkbox(
                                "",
                                key=checkbox_key,
                                label_visibility="collapsed"
                            )

                        with col_article:
                            # Article header
                            st.markdown(f"**{idx}. {article['title']}**")

                            # Article metadata
                            col_meta1, col_meta2 = st.columns(2)

                            with col_meta1:
                                st.caption(f"📰 **Source:** {article['source']}")
                                if article.get('published_date'):
                                    st.caption(f"📅 **Published:** {article['published_date']}")

                            with col_meta2:
                                if article.get('fetched_date'):
                                    st.caption(f"📥 **Fetched:** {article['fetched_date'][:10]}")
                                st.caption(f"🔗 [View Original]({article['url']})")

                            # Article summary/preview
                            if article.get('summary'):
                                with st.expander("📄 Read Summary"):
                                    st.markdown(article['summary'])

                            if article.get('content') and len(article['content']) > 100:
                                with st.expander("📖 Read Full Content"):
                                    # Show preview info if content is long
                                    content_len = len(article['content'])
                                    if content_len > 3000:
                                        st.info(f"📊 Full article: {content_len:,} characters | Showing first 3,000 for preview")
                                        st.markdown(article['content'][:3000] + "\n\n[... content continues ...]")
                                    else:
                                        st.markdown(article['content'])

                        if is_selected:
                            selected_articles.append(article)

                        st.markdown("---")

                    # Step 3: Generation controls
                    if selected_articles:
                        st.markdown("### 📋 Generation Settings")

                        col_gen1, col_gen2, col_gen3 = st.columns(3)

                        with col_gen1:
                            st.metric("Selected Articles", f"{len(selected_articles)}/{len(articles)}")

                        with col_gen2:
                            model_custom = st.radio(
                                "AI Model",
                                ["sonnet", "haiku"],
                                horizontal=True,
                                key="model_custom"
                            )

                        with col_gen3:
                            cost_estimate = 0.12 if model_custom == "sonnet" else 0.01
                            st.metric("Estimated Cost", f"${cost_estimate:.2f}")

                        # Show selected articles summary
                        with st.expander("📄 Selected Articles Summary"):
                            for article in selected_articles:
                                st.markdown(f"- **{article['title']}** ({article['source']})")

                        st.markdown("---")

                        # Custom topic name option
                        st.markdown("**Optional: Custom Article Title**")
                        custom_title = st.text_input(
                            "Leave blank to use default topic name",
                            placeholder=selected_topic['topic_name'],
                            key="custom_title"
                        )

                        # Generate button
                        if st.button("✍️ Generate Article from Selected Articles", type="primary", use_container_width=True):
                            # Write selected article IDs to a temp file for generate.py to use
                            import json
                            import tempfile

                            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                                json.dump({
                                    'article_ids': [a['id'] for a in selected_articles],
                                    'topic_name': custom_title if custom_title else selected_topic['topic_name'],
                                    'topic_id': selected_topic_id
                                }, f)
                                temp_file = f.name

                            st.info(f"Generating article using {len(selected_articles)} selected articles...")

                            with st.spinner("Generating with Claude AI... This may take 1-2 minutes."):
                                # Run generate.py with custom article selection
                                args = [
                                    '--topic', str(selected_topic_id),
                                    '--model', model_custom,
                                    '--custom-articles', temp_file
                                ]

                                success, stdout, stderr = run_pipeline_script_streaming("generate.py", args=args, timeout=600)

                                # Clean up temp file
                                import os
                                try:
                                    os.remove(temp_file)
                                except:
                                    pass

                                if success:
                                    st.success("✅ Article generated successfully!")

                                    # Parse output
                                    gen_stats = parse_generate_output(stdout)

                                    if gen_stats['word_count'] > 0:
                                        col_wc, col_cost_actual = st.columns(2)

                                        with col_wc:
                                            st.metric("Word Count", gen_stats['word_count'])

                                        with col_cost_actual:
                                            if gen_stats['cost'] > 0:
                                                st.metric("Actual Cost", f"${gen_stats['cost']:.2f}")

                                    display_script_output(stdout, stderr, show_stdout=True)
                                    st.balloons()
                                else:
                                    st.error("❌ Generation failed!")
                                    st.markdown("**Error details:**")
                                    display_script_output(stdout, stderr)

                    else:
                        st.warning("⚠️ No articles selected. Please select at least one article to generate.")

                else:
                    st.info("No articles found for this subtopic.")

        else:
            st.info("No subtopics with articles found. Fetch and process articles first.")

        db.close()

    except Exception as e:
        st.error(f"Error: {e}")

# ============================================================================
# TAB 4: AUTO-GENERATE TOP TOPICS
# ============================================================================

with tab4:
    st.markdown("### 🤖 Auto-Generate Top Topics")
    st.markdown("Automatically generate articles for high-relevance topics")

    col_filter1, col_filter2 = st.columns(2)

    with col_filter1:
        min_score_auto = st.slider(
            "Minimum SMB Score",
            min_value=0,
            max_value=10,
            value=8,
            help="Only generate for topics with this SMB relevance or higher"
        )

    with col_filter2:
        min_articles_auto = st.slider(
            "Minimum Article Count",
            min_value=1,
            max_value=10,
            value=3,
            help="Only generate for topics with this many source articles or more"
        )

    max_topics = st.slider(
        "Maximum Topics to Generate",
        min_value=1,
        max_value=20,
        value=5,
        help="Limit number of articles to generate (to control costs)"
    )

    model_auto = st.radio(
        "Select AI Model",
        ["sonnet", "haiku"],
        horizontal=True,
        key="model_auto"
    )

    # Preview matching topics
    if st.button("🔍 Preview Matching Topics"):
        try:
            db = Database()

            # Get ungenerated topics matching criteria
            matching_topics = db.get_ungenerated_subtopics(
                min_score=min_score_auto,
                min_articles=min_articles_auto
            )

            # Limit to max_topics
            matching_topics = matching_topics[:max_topics]

            if matching_topics:
                st.success(f"Found **{len(matching_topics)}** topics matching criteria")

                cost_per_article = 0.12 if model_auto == "sonnet" else 0.01
                total_cost = len(matching_topics) * cost_per_article

                st.info(f"💰 **Estimated total cost:** ${total_cost:.2f}")

                # Display topics
                for topic in matching_topics:
                    st.markdown(f"- **{topic['topic_name']}** (ID: {topic['id']}) - SMB: {topic['smb_relevance_score']}/10, Articles: {topic['article_count']}")

            else:
                st.warning("No topics found matching criteria. Try lowering the filters.")

            db.close()

        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown("---")

    # Generate button
    st.warning("⚠️ **Note:** Batch generation can take 5-20 minutes depending on the number of topics. Monitor the progress below.")

    if st.button("🚀 Start Batch Generation", type="primary", use_container_width=True):
        try:
            db = Database()

            # Get topics to generate
            topics_to_generate = db.get_ungenerated_subtopics(
                min_score=min_score_auto,
                min_articles=min_articles_auto
            )[:max_topics]

            if not topics_to_generate:
                st.error("No topics found matching criteria")
                db.close()
            else:
                st.info(f"Starting generation for {len(topics_to_generate)} topics...")

                success_count = 0
                fail_count = 0

                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, topic in enumerate(topics_to_generate):
                    topic_id = topic['id']
                    topic_name = topic['topic_name']

                    status_text.markdown(f"**Generating {i+1}/{len(topics_to_generate)}:** {topic_name}")

                    # Run generation
                    args = ['--topic', str(topic_id), '--model', model_auto]
                    success, stdout, stderr = run_pipeline_script_streaming("generate.py", args=args, timeout=600)

                    if success:
                        success_count += 1
                        st.success(f"✅ Generated: {topic_name}")
                    else:
                        fail_count += 1
                        st.error(f"❌ Failed: {topic_name}")

                    # Update progress
                    progress_bar.progress((i + 1) / len(topics_to_generate))

                status_text.markdown("### Batch Generation Complete!")
                st.balloons()

                col_success, col_fail = st.columns(2)
                with col_success:
                    st.metric("Successful", success_count)
                with col_fail:
                    st.metric("Failed", fail_count)

                db.close()

        except Exception as e:
            st.error(f"Error during batch generation: {e}")

# ============================================================================
# TAB 5: VIEW GENERATED ARTICLES
# ============================================================================

with tab5:
    st.markdown("### 📚 View Generated Articles")

    try:
        output_dir = 'output/generated_articles'

        if not os.path.exists(output_dir):
            st.info("No generated articles yet. Generate your first article using the tabs above!")
        else:
            files = [f for f in os.listdir(output_dir) if f.endswith('.md')]

            if not files:
                st.info("No generated articles yet. Generate your first article using the tabs above!")
            else:
                st.success(f"Found **{len(files)}** generated articles")

                # Sort by creation time (newest first)
                files_with_time = [(f, os.path.getctime(os.path.join(output_dir, f))) for f in files]
                files_sorted = sorted(files_with_time, key=lambda x: x[1], reverse=True)

                for filename, _ in files_sorted:
                    filepath = os.path.join(output_dir, filename)

                    with st.expander(f"📄 {filename}"):
                        # Read file
                        with open(filepath, 'r') as f:
                            content = f.read()

                        # Calculate word count
                        word_count = len(content.split())

                        col_file1, col_file2 = st.columns(2)

                        with col_file1:
                            st.metric("Word Count", word_count)

                        with col_file2:
                            file_size = os.path.getsize(filepath)
                            st.metric("File Size", f"{file_size / 1024:.1f} KB")

                        # Download button
                        st.download_button(
                            label="📥 Download",
                            data=content,
                            file_name=filename,
                            mime="text/markdown",
                            key=f"download_{filename}"
                        )

                        # Preview
                        with st.expander("👁️ Preview"):
                            st.markdown(content)

    except Exception as e:
        st.error(f"Error loading generated articles: {e}")

st.markdown("---")

# ============================================================================
# FOOTER
# ============================================================================

st.info("""
**Tips for Article Generation:**
- Use Sonnet for higher quality, more detailed articles
- Use Haiku for faster, more cost-effective generation
- Topics with 5+ source articles produce the most comprehensive output
- High SMB scores (8-10) are best for small business audiences
""")
