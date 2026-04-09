import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src import db
from src.ui import stage1, stage2, stage3, stage4, stage5

st.set_page_config(
    page_title="Meeting Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

st.markdown("""
<style>
.stage-pill {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    margin-right: 6px;
}
.done   { background: #22c55e; color: #fff; }
.active { background: #3b82f6; color: #fff; }
.locked { background: #e5e7eb; color: #9ca3af; }
</style>
""", unsafe_allow_html=True)

if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = st.query_params.get("project")

with st.sidebar:
    st.markdown("## 🧠 Meeting Intelligence")
    st.divider()

    with st.expander("➕ New Project"):
        name = st.text_input("Name", placeholder="My Project")
        if st.button("Create", type="primary") and name.strip():
            p = db.create_project(name.strip())
            st.session_state.current_project_id = p["id"]
            st.query_params["project"] = p["id"]
            st.rerun()

    st.markdown("### Projects")
    projects = db.list_projects()

    if not projects:
        st.info("No projects yet.")
    else:
        for p in projects:
            active = p["id"] == st.session_state.current_project_id
            label = f"{'▶ ' if active else ''}{p['name']}  (Stage {p.get('current_stage', 1)}/5)"
            if st.button(label, key=f"p_{p['id']}"):
                st.session_state.current_project_id = p["id"]
                st.query_params["project"] = p["id"]
                st.rerun()

    st.divider()
    if st.session_state.current_project_id:
        with st.expander("🗑️ Delete project"):
            if st.button("Delete", type="secondary"):
                db.delete_project(st.session_state.current_project_id)
                st.session_state.current_project_id = None
                st.query_params.clear()
                st.rerun()

    st.markdown("---")
    oai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gem_key = os.getenv("GEMINI_API_KEY", "").strip()
    if oai_key and not oai_key.startswith("sk-..."):
        st.caption("🟢 Backend: OpenAI GPT-4o")
    elif gem_key:
        st.caption("🟢 Backend: Google Gemini")
    else:
        st.error("No AI key — set OPENAI_API_KEY or GEMINI_API_KEY in .env")

pid = st.session_state.current_project_id

if not pid:
    st.markdown("# Welcome to Meeting Intelligence")
    st.markdown("Turn client meeting transcripts into scope, sprint plans, and Jira issues — with a human approving every step.")
    st.markdown("**Create a project in the sidebar to get started →**")
    st.stop()

project = db.get_project(pid)
if not project:
    st.error("Project not found.")
    st.session_state.current_project_id = None
    st.stop()

st.title(f"📋 {project['name']}")
try:
    dt = datetime.fromisoformat(project.get("created_at", ""))
    st.caption(f"Created {dt.strftime('%d %b %Y, %H:%M')}")
except Exception:
    pass

STAGES = ["1 · Analysis", "2 · Clarification", "3 · Scope of Work", "4 · Sprint Plan", "5 · Jira Sync"]
APPROVED = [
    project.get("stage1_approved", 0),
    project.get("stage2_approved", 0),
    project.get("stage3_approved", 0),
    project.get("stage4_approved", 0),
    project.get("stage5_approved", 0),
]
current = project.get("current_stage", 1)

html = ""
for i, label in enumerate(STAGES):
    if APPROVED[i]:
        html += f'<span class="stage-pill done">✓ {label}</span>'
    elif i + 1 == current:
        html += f'<span class="stage-pill active">▶ {label}</span>'
    else:
        html += f'<span class="stage-pill locked">🔒 {label}</span>'
st.markdown(html, unsafe_allow_html=True)
st.divider()

tabs = st.tabs(["📄 Stage 1", "❓ Stage 2", "📃 Stage 3", "📅 Stage 4", "🚀 Stage 5"])

with tabs[0]:
    stage1.render(project)
with tabs[1]:
    project = db.get_project(pid)
    stage2.render(project)
with tabs[2]:
    project = db.get_project(pid)
    stage3.render(project)
with tabs[3]:
    project = db.get_project(pid)
    stage4.render(project)
with tabs[4]:
    project = db.get_project(pid)
    stage5.render(project)
