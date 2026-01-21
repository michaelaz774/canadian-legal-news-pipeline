"""
Subprocess execution utilities for Streamlit web interface
Provides safe execution of pipeline scripts with error handling and real-time streaming.
Updated: 2026-01-21
"""

import subprocess
import sys
import streamlit as st
import time
import re
from typing import Tuple, Optional, List, Dict, Any


def run_pipeline_script(
    script_name: str,
    args: Optional[List[str]] = None,
    timeout: int = 600
) -> Tuple[bool, str, str]:
    """
    Run a pipeline script (fetch.py, compile.py, generate.py) safely.

    Args:
        script_name: Name of script (e.g., "fetch.py")
        args: List of command line arguments (optional)
        timeout: Timeout in seconds (default: 600 = 10 minutes)

    Returns:
        Tuple of (success: bool, stdout: str, stderr: str)

    Example:
        success, stdout, stderr = run_pipeline_script("fetch.py")
        if success:
            st.success("Fetch completed successfully!")
            st.code(stdout)
        else:
            st.error("Fetch failed!")
            st.code(stderr)
    """
    # Build command using sys.executable to ensure correct Python interpreter
    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)

    # Pass Streamlit secrets as environment variables
    import os
    env = os.environ.copy()
    if hasattr(st, 'secrets'):
        for key, value in st.secrets.items():
            if isinstance(value, str):
                env[key] = value

    try:
        # Run the script and capture output
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=None,  # Use current working directory
            env=env  # Pass environment variables including secrets
        )

        success = result.returncode == 0
        return success, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        error_msg = f"Script timed out after {timeout} seconds"
        return False, "", error_msg

    except FileNotFoundError:
        error_msg = f"Script not found: {script_name}"
        return False, "", error_msg

    except Exception as e:
        error_msg = f"Error running script: {str(e)}"
        return False, "", error_msg


def run_pipeline_script_streaming(
    script_name: str,
    args: Optional[List[str]] = None,
    timeout: int = 600
) -> Tuple[bool, str, str]:
    """
    Run a pipeline script with real-time streaming output for better observability.

    Shows live progress updates in the Streamlit UI as the script executes.

    Args:
        script_name: Name of script (e.g., "fetch.py")
        args: List of command line arguments (optional)
        timeout: Timeout in seconds (default: 600 = 10 minutes)

    Returns:
        Tuple of (success: bool, stdout: str, stderr: str)

    Features:
        - Real-time output streaming
        - Progress tracking with status indicators
        - Live log display
        - Error highlighting
        - Timeout handling
    """
    # Build command with unbuffered output for real-time streaming
    cmd = [sys.executable, '-u', script_name]
    if args:
        cmd.extend(args)

    # Pass Streamlit secrets as environment variables
    import os
    env = os.environ.copy()

    # Force unbuffered output
    env['PYTHONUNBUFFERED'] = '1'

    if hasattr(st, 'secrets'):
        for key, value in st.secrets.items():
            if isinstance(value, str):
                env[key] = value

    # Create containers for live updates
    status_container = st.container()
    progress_container = st.container()
    log_container = st.container()

    stdout_lines = []
    stderr_lines = []

    try:
        # Start process with pipes for real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            env=env,
            universal_newlines=True
        )

        start_time = time.time()

        # Progress tracking variables
        current_status = "Starting..."
        articles_processed = 0
        total_articles = 0
        errors_count = 0

        # Create status display
        with status_container:
            status_text = st.empty()
            status_text.info(f"⚙️ {current_status}")

        # Create progress bar (initially hidden)
        with progress_container:
            progress_bar = st.empty()
            progress_text = st.empty()

        # Create live log display
        with log_container:
            st.markdown("### 📋 Live Output")
            log_display = st.empty()

        # Read output in real-time
        while True:
            # Check timeout
            if time.time() - start_time > timeout:
                process.kill()
                return False, '\n'.join(stdout_lines), "Process timed out"

            # Read stdout line
            line = process.stdout.readline()

            if line:
                stdout_lines.append(line.rstrip())

                # Parse progress indicators
                progress_info = parse_progress_line(line)
                if progress_info:
                    if 'status' in progress_info:
                        current_status = progress_info['status']
                        status_text.info(f"⚙️ {current_status}")

                    if 'current' in progress_info and 'total' in progress_info:
                        articles_processed = progress_info['current']
                        total_articles = progress_info['total']

                        # Update progress bar
                        if total_articles > 0:
                            progress_pct = articles_processed / total_articles
                            progress_bar.progress(progress_pct)
                            progress_text.text(f"Progress: {articles_processed}/{total_articles} ({progress_pct*100:.0f}%)")

                    if 'error' in progress_info:
                        errors_count += 1

                # Update log display (last 20 lines)
                recent_logs = stdout_lines[-20:]
                log_text = format_log_lines(recent_logs)
                log_display.code(log_text, language="text")

            # Check if process finished
            if process.poll() is not None:
                break

        # Read any remaining output
        remaining_out, remaining_err = process.communicate()
        if remaining_out:
            stdout_lines.extend(remaining_out.splitlines())
        if remaining_err:
            stderr_lines.extend(remaining_err.splitlines())

        # Final status update
        success = process.returncode == 0

        with status_container:
            if success:
                status_text.success(f"✅ Completed successfully! ({len(stdout_lines)} lines processed)")
                if errors_count > 0:
                    st.warning(f"⚠️ Completed with {errors_count} errors")
            else:
                status_text.error(f"❌ Failed with return code {process.returncode}")

        # Show full output in expander
        if stdout_lines:
            with st.expander("📄 Full Output Log", expanded=False):
                st.code('\n'.join(stdout_lines), language="text")

        if stderr_lines:
            with st.expander("⚠️ Error Log", expanded=True):
                st.code('\n'.join(stderr_lines), language="text")

        return success, '\n'.join(stdout_lines), '\n'.join(stderr_lines)

    except Exception as e:
        error_msg = f"Error running script: {str(e)}"
        with status_container:
            st.error(f"❌ {error_msg}")
        return False, '\n'.join(stdout_lines), error_msg


def parse_progress_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse a log line to extract progress information.

    Recognizes patterns like:
    - "Processing 5/60 articles"
    - "Processing: Article Title"
    - "✓ Success" / "✗ Failed"
    - Progress bars from tqdm
    """
    info = {}

    # Extract progress from "X/Y" pattern
    match = re.search(r'(\d+)/(\d+)', line)
    if match:
        info['current'] = int(match.group(1))
        info['total'] = int(match.group(2))

    # Extract status from "Processing:" lines
    if 'Processing:' in line or 'Processing ' in line:
        # Extract article title or description
        parts = line.split('Processing:', 1)
        if len(parts) > 1:
            info['status'] = f"Processing: {parts[1].strip()[:60]}..."
        else:
            info['status'] = "Processing..."

    # Detect errors
    if '✗' in line or 'ERROR' in line or 'Failed' in line:
        info['error'] = True

    # Detect success
    if '✓' in line or 'success' in line.lower():
        info['success'] = True

    # Extract from fetching messages
    if 'Fetching' in line:
        info['status'] = line.strip()

    # Extract from generation messages
    if 'Generating' in line or 'Synthesizing' in line:
        info['status'] = line.strip()

    return info if info else None


def format_log_lines(lines: List[str]) -> str:
    """
    Format log lines with highlighting for errors and successes.
    """
    formatted = []
    for line in lines:
        # Highlight errors
        if '✗' in line or 'ERROR' in line:
            formatted.append(f"❌ {line}")
        # Highlight successes
        elif '✓' in line:
            formatted.append(f"✅ {line}")
        # Normal line
        else:
            formatted.append(f"   {line}")

    return '\n'.join(formatted)


def display_script_output(stdout: str, stderr: str, show_stdout: bool = True):
    """
    Display script output in Streamlit with formatting.

    Args:
        stdout: Standard output from script
        stderr: Standard error from script
        show_stdout: Whether to show stdout (default: True)
    """
    if stdout and show_stdout:
        with st.expander("📋 Output Log", expanded=True):
            st.code(stdout, language="text")

    if stderr:
        with st.expander("⚠️ Error Log", expanded=True):
            st.code(stderr, language="text")


def parse_fetch_output(stdout: str) -> dict:
    """
    Parse output from fetch.py to extract statistics.

    Returns:
        Dictionary with keys: inserted, skipped, total_articles
    """
    stats = {"inserted": 0, "skipped": 0, "total_articles": 0}

    try:
        lines = stdout.split('\n')
        for line in lines:
            if "Inserted:" in line and "Skipped:" in line:
                # Example: "Inserted: 5, Skipped: 15"
                parts = line.split(',')
                if len(parts) >= 2:
                    inserted_part = parts[0].strip()
                    skipped_part = parts[1].strip()

                    if "Inserted:" in inserted_part:
                        stats["inserted"] = int(inserted_part.split(':')[1].strip())
                    if "Skipped:" in skipped_part:
                        stats["skipped"] = int(skipped_part.split(':')[1].strip())

            if "Total articles in database:" in line:
                # Example: "Total articles in database: 80"
                parts = line.split(':')
                if len(parts) >= 2:
                    stats["total_articles"] = int(parts[1].strip())

    except Exception as e:
        st.warning(f"Could not parse fetch output: {e}")

    return stats


def parse_compile_output(stdout: str) -> dict:
    """
    Parse output from compile.py to extract statistics.

    Returns:
        Dictionary with keys: processed_count, topics_created
    """
    stats = {"processed_count": 0, "topics_created": 0}

    try:
        lines = stdout.split('\n')
        for line in lines:
            if "Processed" in line and "articles" in line:
                # Example: "Processed 5 articles"
                parts = line.split()
                if len(parts) >= 2:
                    stats["processed_count"] = int(parts[1])

            if "Created" in line and "topics" in line:
                # Example: "Created 12 topics"
                parts = line.split()
                if len(parts) >= 2:
                    stats["topics_created"] = int(parts[1])

    except Exception as e:
        st.warning(f"Could not parse compile output: {e}")

    return stats


def parse_generate_output(stdout: str) -> dict:
    """
    Parse output from generate.py to extract statistics.

    Returns:
        Dictionary with keys: word_count, cost, output_file
    """
    stats = {"word_count": 0, "cost": 0.0, "output_file": ""}

    try:
        lines = stdout.split('\n')
        for line in lines:
            if "Word count:" in line:
                # Example: "Word count: 2311"
                parts = line.split(':')
                if len(parts) >= 2:
                    stats["word_count"] = int(parts[1].strip())

            if "Cost:" in line or "cost:" in line:
                # Example: "Cost: $0.12"
                parts = line.split('$')
                if len(parts) >= 2:
                    stats["cost"] = float(parts[1].strip())

            if "Saved to:" in line or "output/" in line:
                # Example: "Saved to: output/generated_articles/article_123.md"
                stats["output_file"] = line.strip()

    except Exception as e:
        st.warning(f"Could not parse generate output: {e}")

    return stats
