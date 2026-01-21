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
    Run a pipeline script with real-time output streaming.

    Args:
        script_name: Name of script (e.g., "fetch.py")
        args: List of command line arguments (optional)
        timeout: Timeout in seconds (default: 600 = 10 minutes)

    Returns:
        Tuple of (success: bool, stdout: str, stderr: str)
    """
    # Build command with unbuffered output
    cmd = [sys.executable, '-u', script_name]
    if args:
        cmd.extend(args)

    # Pass Streamlit secrets as environment variables
    import os
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'

    if hasattr(st, 'secrets'):
        for key, value in st.secrets.items():
            if isinstance(value, str):
                env[key] = value

    # Estimate time based on script
    if 'fetch' in script_name:
        estimated_time = "30-60 seconds"
    elif 'compile' in script_name:
        estimated_time = "2-5 minutes"
    elif 'generate' in script_name:
        estimated_time = "1-3 minutes"
    else:
        estimated_time = "a few minutes"

    st.info(f"⏳ Running {script_name}... This typically takes {estimated_time}.")
    st.markdown("---")

    # Create a container for real-time output
    output_container = st.container()

    stdout_lines = []
    stderr_lines = []

    try:
        # Start the process with Popen for real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            env=env
        )

        # Read output in real-time
        import time as time_module

        start_time = time_module.time()

        while True:
            # Check for timeout
            if time_module.time() - start_time > timeout:
                process.kill()
                st.error(f"⏱️ Process timed out after {timeout} seconds")
                return False, "\n".join(stdout_lines), f"Script timed out after {timeout} seconds"

            # Read stdout line by line
            line = process.stdout.readline()
            if line:
                line = line.rstrip()
                stdout_lines.append(line)
                # Display the line in real-time
                with output_container:
                    st.text(line)

            # Check if process has finished
            if process.poll() is not None:
                # Read any remaining output
                for line in process.stdout:
                    line = line.rstrip()
                    stdout_lines.append(line)
                    with output_container:
                        st.text(line)
                break

            # Small sleep to prevent CPU spinning
            time_module.sleep(0.1)

        # Capture any stderr
        stderr_output = process.stderr.read()
        if stderr_output:
            stderr_lines = stderr_output.strip().split('\n')

        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)
        success = process.returncode == 0

    except Exception as e:
        st.error(f"❌ Error running script: {str(e)}")
        return False, "\n".join(stdout_lines), str(e)

    # Show results after completion
    st.markdown("---")
    if success:
        st.success("✅ Completed successfully!")
    else:
        st.error("❌ Process failed!")
        if stderr:
            st.error("Error details:")
            with st.expander("Error Log", expanded=True):
                st.code(stderr, language="text")

    # Show full output in expander for reference
    if stdout:
        with st.expander("📄 Full Output Log (Click to expand)", expanded=False):
            st.code(stdout, language="text")

    if stderr and success:
        with st.expander("⚠️ Warnings", expanded=False):
            st.code(stderr, language="text")

    return success, stdout, stderr


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
