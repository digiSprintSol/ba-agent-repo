import os
import re
import time
import streamlit as st
from dotenv import load_dotenv
from parsers import extract_text
from utils import Story, paginate, make_excel, make_docx
from llm_client import extract_modules, generate_stories

load_dotenv()

# ---- Initialize Session State ----
if "modules" not in st.session_state:
    st.session_state.modules = []
if "current_module_index" not in st.session_state:
    st.session_state.current_module_index = 0
if "all_stories" not in st.session_state:
    st.session_state.all_stories = []
if "pending_batch" not in st.session_state:
    st.session_state.pending_batch = []
if "parsed_text" not in st.session_state:
    st.session_state.parsed_text = ""

st.set_page_config(page_title="BA Agent – Gemini", layout="wide")
st.title("📄 BA Agent — Module-wise User Story Generator")

# Sidebar
with st.sidebar:
    if "page_size" not in st.session_state:
        st.session_state.page_size = 5
    if "batch_size" not in st.session_state:
        st.session_state.batch_size = 10

    st.session_state.page_size = st.number_input(
        "Rows per page", min_value=1, max_value=20, value=st.session_state.page_size
    )
    st.session_state.batch_size = st.number_input(
        "Batch size per module", min_value=5, max_value=30, value=st.session_state.batch_size
    )

# ---- File Upload ----
uploads = st.file_uploader("Upload requirement files",
    type=["docx", "pdf", "txt", "md", "csv", "xlsx"],
    accept_multiple_files=True
)

if uploads:
    texts = []
    for f in uploads:
        texts.append(extract_text(f))
    st.session_state.parsed_text = "\n\n".join(texts)
    st.success("✅ Files parsed successfully!")

# ---- Step 1: Extract Modules ----
if st.button("🔍 Extract Modules"):
    if not st.session_state.parsed_text.strip():
        st.warning("Please upload requirement files first.")
    else:
        st.session_state.modules = extract_modules(st.session_state.parsed_text)
        st.session_state.current_module_index = 0
        st.success(f"✅ Found {len(st.session_state.modules)} modules!")

if st.session_state.modules:
    st.subheader("📦 Modules Extracted")
    for i, m in enumerate(st.session_state.modules):
        mark = "➡️" if i == st.session_state.current_module_index else " "
        st.write(f"{mark} **{m['module']}** ({', '.join(m.get('features', []))})")

# ---- Custom Instruction ----
custom_req = st.text_area("Custom requirement / instruction", height=150)

# ---- Step 2: Generate Stories ----
if st.button("Generate Next Batch"):
    if not st.session_state.modules:
        st.warning("Please extract modules first.")
    else:
        current_module = st.session_state.modules[st.session_state.current_module_index]["module"]
        with st.spinner(f"Generating stories for module: {current_module}..."):
            data = generate_stories(st.session_state.parsed_text, current_module, st.session_state.batch_size, custom_req)

            new_stories = []
            for item in data:
                ac = item.get("acceptance_criteria", [])
                if isinstance(ac, str):
                    ac = [p.strip() for p in re.split(r"[\n;•\-]+", ac) if p.strip()]
                elif not isinstance(ac, list):
                    ac = []

                new_stories.append(
                    Story(
                        module=item.get("module", "General"),
                        title=item.get("title", "Untitled"),
                        description=item.get("description", ""),
                        acceptance_criteria=ac
                    )
                )

            st.session_state.pending_batch = new_stories

        if new_stories:
            st.success(f"✅ Generated {len(new_stories)} new stories (pending approval)")
        else:
            st.warning("⚠️ No user stories generated.")

# ---- Step 3: Approve Batch ----
if st.session_state.pending_batch:
    st.subheader("✅ Pending Approval")
    st.table([{
        "Module": s.module,
        "Title": s.title,
        "Description": s.description,
        "Acceptance Criteria": "\n".join(s.acceptance_criteria)
    } for s in st.session_state.pending_batch])

    if st.button("Approve Batch"):
        st.session_state.all_stories.extend(st.session_state.pending_batch)
        st.session_state.pending_batch = []
        total_approved = len(st.session_state.all_stories)
        st.success(f"🎉 Approved! Total approved user stories so far: **{total_approved}** ✅")
        # Move to next module
        if st.session_state.current_module_index < len(st.session_state.modules) - 1:
            st.session_state.current_module_index += 1
        else:
            st.success("🎉 All modules completed!")

# ---- Step 4: Display Approved Stories ----
if st.session_state.all_stories:
    st.subheader("📑 Approved User Stories")
    total = len(st.session_state.all_stories)
    total_pages = (total +  st.session_state.page_size - 1) //  st.session_state.page_size
    current_page = st.session_state.get("page", 0)

    page_items = paginate(st.session_state.all_stories,  st.session_state.page_size, current_page)
    st.table([{
        "#": i + 1 + current_page *  st.session_state.page_size,
        "Module": s.module,
        "Title": s.title,
        "Description": s.description,
        "Acceptance Criteria": "\n".join(s.acceptance_criteria)
    } for i, s in enumerate(page_items)])

    # Pagination buttons
    nav_cols = st.columns(total_pages + 2)
    if nav_cols[0].button("⬅️ Prev", disabled=current_page <= 0):
        st.session_state.page -= 1
    for i in range(total_pages):
        if nav_cols[i + 1].button(str(i + 1), key=f"page_{i}"):
            st.session_state.page = i
    if nav_cols[-1].button("Next ➡️", disabled=current_page >= total_pages - 1):
        st.session_state.page += 1

    # Download buttons
    st.download_button("⬇️ Excel", make_excel(st.session_state.all_stories), "user_stories.xlsx")
    st.download_button("⬇️ Word", make_docx(st.session_state.all_stories), "user_stories.docx")
