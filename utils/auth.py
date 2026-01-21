"""
Authentication module for Streamlit web interface
Provides simple password protection for the application
"""

import streamlit as st
import os


def check_password():
    """
    Returns True if user enters correct password.
    Password is stored in Streamlit secrets or environment variable.

    SECURITY NOTE:
    - For local development, set PASSWORD environment variable in .env
    - For Railway deployment, set PASSWORD in Railway dashboard
    - Default password is "changeme" (for development only)
    """

    def password_entered():
        """Check if entered password is correct"""
        # Try to get password from Streamlit secrets, then environment, then default
        try:
            correct_password = st.secrets["PASSWORD"]
        except (FileNotFoundError, KeyError):
            # Secrets file doesn't exist or PASSWORD not in secrets
            correct_password = os.environ.get("PASSWORD", "changeme")

        if st.session_state["password"] == correct_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password in session
        else:
            st.session_state["password_correct"] = False

    # First run - no password entered yet
    if "password_correct" not in st.session_state:
        st.text_input(
            "🔐 Enter Password",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.info("Enter password to access the Legal News Pipeline")
        return False

    # Password was incorrect
    elif not st.session_state["password_correct"]:
        st.text_input(
            "🔐 Enter Password",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.error("😕 Incorrect password")
        return False

    # Password correct
    else:
        return True
