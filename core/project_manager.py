import os
import json
from core.utils import Story

BASE_DIR = "projects"

def ensure_base_dir():
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR)

def ensure_project(project_name: str):
    ensure_base_dir()
    project_path = os.path.join(BASE_DIR, project_name)
    if not os.path.exists(project_path):
        os.makedirs(project_path)
    return project_path

def save_user_stories(project_name, stories):
    """Save user stories for a project as JSON."""
    project_path = ensure_project(project_name)
    file_path = os.path.join(project_path, "user_stories.json")

    serializable = []
    for s in stories:
        if isinstance(s, Story):
            serializable.append({
                "module": s.module,
                "title": s.title,
                "description": s.description,
                "acceptance_criteria": s.acceptance_criteria
            })
        elif isinstance(s, dict):
            serializable.append(s)
        else:
            raise TypeError(f"Unsupported story type: {type(s)}")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2)

    return file_path

def load_user_stories(project_name):
    """Load user stories for a project as Story objects."""
    project_path = ensure_project(project_name)
    file_path = os.path.join(project_path, "user_stories.json")

    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [Story(**s) if isinstance(s, dict) else s for s in data]

def save_test_cases(project_name, module_name, test_cases):
    """Save generated test cases to JSON."""
    project_path = ensure_project(project_name)
    file_path = os.path.join(project_path, f"{module_name}_testcases.json")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(test_cases, f, indent=2)

    return file_path

def load_test_cases(project_name, module_name):
    """Load saved test cases for a module."""
    project_path = ensure_project(project_name)
    file_path = os.path.join(project_path, f"{module_name}_testcases.json")

    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def list_projects():
    ensure_base_dir()
    return [d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]
