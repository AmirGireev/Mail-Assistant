import os

from dotenv import load_dotenv

# load .env
load_dotenv()


# read setting
def get(key, default=None):
    # env first
    if key in os.environ:
        return os.environ[key]
    # streamlit secrets
    try:
        import streamlit as st

        return st.secrets.get(key, default)
    except Exception:
        return default