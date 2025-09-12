import json
import re
import streamlit as st
from core import project_manager
from core.llm_client import extract_json_from_text, BA_MODEL, genai, get_text
from core.utils import make_testcase_excel, render_paginated_table

def load_prompt(file_path: str) -> str:
    """Load test case generation prompt from file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def _normalize_testcases(raw_cases, module_name: str, starting_id: int):
    """
    Ensure keys exist and steps are properly formatted, skipping invalid items.
    Generates unique testcase_id starting from the given number.
    """
    required = [
        "scenario_id", "module", "test_scenario", "testcase_id", "testcase_title",
        "pre_condition", "test_data", "steps", "expected_result", "actual_result",
        "status", "comments", "priority", "positive_negative", "end_to_end"
    ]

    out = []
    tc_num = starting_id

    if not isinstance(raw_cases, list):
        raw_cases = [raw_cases] if raw_cases else []

    for c in raw_cases:
        if not isinstance(c, dict):
            continue

        d = {}
        d["module"] = c.get("module") or module_name
        d["scenario_id"] = c.get("scenario_id") or ""
        d["testcase_id"] = c.get("testcase_id") or f"TC_{tc_num:03d}"
        d["test_scenario"] = c.get("test_scenario") or ""
        d["testcase_title"] = c.get("testcase_title") or d["test_scenario"] or f"Test {d['testcase_id']}"
        d["pre_condition"] = c.get("pre_condition") or ""
        d["test_data"] = c.get("test_data", "")

        steps = c.get("steps") or []
        if isinstance(steps, str):
            steps = [s.strip() for s in re.split(r"[\n\r\t•\-]+", steps) if s.strip()]
        d["steps"] = steps

        d["expected_result"] = c.get("expected_result") or ""
        d["actual_result"] = c.get("actual_result", "")
        d["status"] = c.get("status", "")
        d["comments"] = c.get("comments", "")
        d["priority"] = c.get("priority", "Medium")
        d["positive_negative"] = c.get("positive_negative") or ""
        d["end_to_end"] = c.get("end_to_end") or "No"

        for k in required:
            d.setdefault(k, "")

        out.append(d)
        tc_num += 1

    return out

def _extract_tc_num(tc_id: str) -> int:
    """Extract numeric part of testcase ID (e.g., TC_042 -> 42)."""
    if not tc_id:
        return 0
    m = re.search(r"TC[_\-]?(\d+)", tc_id)
    return int(m.group(1)) if m else 0

def _dedupe_and_reassign_ids(testcases):
    """Deduplicate and renumber all testcases sequentially (TC_001 …)."""
    seen = set()
    unique = []
    for tc in testcases:
        key = (
            tc.get("scenario_id"),
            tc.get("testcase_title"),
            tc.get("expected_result"),
            tuple(tc.get("steps", []))
        )
        if key not in seen:
            seen.add(key)
            unique.append(tc)

    # Reassign testcase_id sequentially
    for i, tc in enumerate(unique, start=1):
        tc["testcase_id"] = f"TC_{i:03d}"

    return unique

def find_valid_json_substrings(text: str):
    """
    Finds and extracts all valid JSON objects within a string.
    This is useful for truncated JSON arrays.
    """
    valid_objects = []
    stack = []
    start_index = -1
    
    for i, char in enumerate(text):
        if char == '{':
            if not stack:
                start_index = i
            stack.append('{')
        elif char == '}':
            if stack:
                stack.pop()
                if not stack and start_index != -1:
                    obj_string = text[start_index:i+1]
                    try:
                        valid_objects.append(json.loads(obj_string))
                    except json.JSONDecodeError:
                        pass
                    start_index = -1
    
    return valid_objects

def generate_test_cases_for_module(module_name: str, stories: list, custom_instruction: str = ""):
    base_prompt = load_prompt("prompts/test_cases.txt")

    module_stories = [
        s if isinstance(s, dict) else s.__dict__
        for s in stories
        if (s.get("module") if isinstance(s, dict) else getattr(s, "module", None)) == module_name
    ]

    story_text = "\n\n".join([
        f"User Story {i+1}:\nTitle: {s.get('title')}\nDescription: {s.get('description')}\nAcceptance Criteria:\n{json.dumps(s.get('acceptance_criteria', []), indent=2)}"
        for i, s in enumerate(module_stories)
    ]) or "No stories available for this module."

    model = genai.GenerativeModel(
        BA_MODEL,
        generation_config={
            "temperature": 0.2,
            "top_p": 0.9,
            "response_mime_type": "application/json",
        },
    )

    all_cases = []
    num_iterations = 1
    print("line 144"+custom_instruction)
    for i in range(num_iterations):
        with st.spinner(f"Generating test case batch {i+1} of {num_iterations}..."):
            chunking_instruction = f"""
            Generate approximately all possible  new test cases.
            Do not duplicate any of the following already generated test cases:
            {json.dumps(all_cases)}
            """
            prompt = f"""{base_prompt}
            Project Module: {module_name}
            The following user stories belong to this module:
            {story_text}
            Additional Instruction:
            {custom_instruction}
            {chunking_instruction}
            """

            try:
                resp = model.generate_content(prompt)
                text = get_text(resp)
                
                # First, try to get a complete JSON array
                cases = extract_json_from_text(text)
                
                if isinstance(cases, list) and cases:
                    normalized_cases = _normalize_testcases(cases, module_name, len(all_cases) + 1)
                    all_cases.extend(normalized_cases)
                    
                else:
                    # If it's not a complete array, try to find valid objects within the text.
                    valid_sub_cases = find_valid_json_substrings(text)
                    if valid_sub_cases:
                        normalized_sub_cases = _normalize_testcases(valid_sub_cases, module_name, len(all_cases) + 1)
                        all_cases.extend(normalized_sub_cases)
                        st.warning(f"⚠️ Generation stopped after batch {i+1} due to an incomplete response. Displaying partial results.")
                    else:
                        pass  # No valid JSON found, skip this iteration                    
                    return all_cases
            
            except Exception as e:
                pass
                return all_cases
    
    return all_cases

def run():
    st.title("🧪 Test Case Agent — Module-wise Generator")

    if "pending_testcases" not in st.session_state:
        st.session_state["pending_testcases"] = []
    if "all_testcases" not in st.session_state:
        st.session_state["all_testcases"] = []

    projects = project_manager.list_projects()
    if not projects:
        st.warning("⚠️ No projects found. Please create user stories first in BA Agent.")
        return

    project_name = st.selectbox("Select Project", projects)
    stories = project_manager.load_user_stories(project_name)
    if not stories:
        st.warning("⚠️ No user stories found for this project.")
        return

    def _get(obj, attr):
        return getattr(obj, attr, None) if not isinstance(obj, dict) else obj.get(attr)

    modules = sorted({_get(s, "module") for s in stories if _get(s, "module")})
    selected_module = st.selectbox("Select Module", modules)

    custom_instruction = st.text_area(
        "Custom instruction (optional)",
        height=120,
        placeholder="E.g., include boundary validations, accessibility checks, negative flows..."
    )

    if st.button("Generate Test Cases"):
        new_cases = generate_test_cases_for_module(selected_module, stories, custom_instruction)
        st.session_state["pending_testcases"] = new_cases
        st.session_state["selected_module_for_tc"] = selected_module
        st.session_state["tc_page"] = 0
        if st.session_state["pending_testcases"]:
            st.success(f"✅ Generated {len(new_cases)} new test cases (pending approval) for **{selected_module}**")
        else:
            st.warning("⚠️ No test cases were generated. Please try again.")                
    # --- Show Generated Test Cases ---
    if st.session_state.get("pending_testcases") and st.session_state.get("selected_module_for_tc") == selected_module:
        st.markdown("---")
        if st.session_state["pending_testcases"]:
            st.subheader("🕒 Pending Approval")
            tc_rows = st.session_state["pending_testcases"]
            render_paginated_table(
            tc_rows,
            columns={
                "scenario_id": "Scenario ID",
                "module": "Module",
                "testcase_title": "Title",
                "priority": "Priority",
                "expected_result": "Expected Result"
            },
            page_state_key="tc_page",
            page_size=st.sidebar.number_input("Rows per page", min_value=1, max_value=20, value=5)
        )
            excel_buf = make_testcase_excel(tc_rows, project_name, selected_module)
            st.download_button(
            f"⬇️ Download {selected_module} Test Cases (Excel)",
            excel_buf,
            file_name=f"{project_name}_{selected_module}_testcases.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        if st.button("Approve Pending Test Cases"):
            def _tc_key(tc):
                return f"{tc.get('scenario_id')}|{tc.get('testcase_title')}"

            existing_keys = {_tc_key(tc) for tc in st.session_state["all_testcases"]}
            unique_new = [tc for tc in tc_rows if _tc_key(tc) not in existing_keys]
            # Find the current max number across approved
            def _extract_num(tc_id: str) -> int:
                m = re.search(r"TC[_\-]?(\d+)", tc_id or "")
                return int(m.group(1)) if m else 0

            current_max = 0
            for tc in st.session_state["all_testcases"]:
                current_max = max(current_max, _extract_num(tc.get("testcase_id", "")))

    # Assign new global IDs
            next_id = current_max + 1
            for tc in unique_new:
                tc["testcase_id"] = f"TC_{next_id:03d}"
                next_id += 1
            st.session_state["all_testcases"].extend(unique_new)
            st.session_state["all_testcases"] = _dedupe_and_reassign_ids(st.session_state["all_testcases"])
            # project_manager.save_test_cases(project_name, selected_module, st.session_state["pending_testcases"])
            st.session_state["pending_testcases"] = []
            st.success(f"🎉 Approved {len(unique_new)} test cases for {selected_module}")

    if st.session_state["all_testcases"]:
            st.markdown("---")
            st.subheader("✅ Approved Test Cases (All Modules)")
            approved_rows = st.session_state["all_testcases"]
            render_paginated_table(
            approved_rows,
            columns={
                "scenario_id": "Scenario ID",
                "module": "Module",
                "testcase_title": "Title",
                "priority": "Priority",
                "expected_result": "Expected Result"
            }, 
            page_state_key="approved_tc_page",
            page_size=st.sidebar.number_input("Rows per page (approved)", min_value=1, max_value=20, value=5)
        )
            
            def _tc_key(tc):
                return f"{tc.get('scenario_id')}|{tc.get('testcase_title')}"
            seen = set()
            unique_approved_cases = []
            for tc in approved_rows:
                key = _tc_key(tc)
                if key not in seen:
                    unique_approved_cases.append(tc)
                    seen.add(key)
            deduped = _dedupe_and_reassign_ids(st.session_state["all_testcases"])
            all_excel_buf = make_testcase_excel(deduped, project_name, "ALL")
            if approved_rows:
                st.download_button(
            "⬇️ Download All Approved Test Cases (Excel)",
            all_excel_buf,
            file_name=f"{project_name}_ALL_testcases.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )  