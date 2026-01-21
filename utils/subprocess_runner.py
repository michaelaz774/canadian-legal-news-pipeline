"""
Subprocess execution utilities for Streamlit web interface
Provides safe execution of pipeline scripts with error handling
"""

import subprocess
import sys
import streamlit as st
from typing import Tuple, Optional, List


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
