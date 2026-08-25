"""Minimal Streamlit entry point for the analytics dashboard service."""

import streamlit as st

from app import APP_NAME


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon=None, layout="wide")
    st.title(APP_NAME)
    st.caption("Infrastructure ready.")


if __name__ == "__main__":
    main()
