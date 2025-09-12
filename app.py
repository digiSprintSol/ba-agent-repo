import streamlit as st
from agents import ba_agent, test_case_agent
from core import project_manager  # add this import


st.set_page_config(page_title="AI Agent Platform", layout="wide")

st.sidebar.title("Navigation")
# Project selection
tab = st.sidebar.radio("Choose an Agent:", ["BA Agent", "Test Case Agent"])

if tab == "BA Agent":
    ba_agent.run()
elif tab == "Test Case Agent":
    test_case_agent.run()
