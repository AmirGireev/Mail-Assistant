import os
from dotenv import load_dotenv
load_dotenv()

def get(key, default=None):
    if key in os.environ:
        return os.environ[key]
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default