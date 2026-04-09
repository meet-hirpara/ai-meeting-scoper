# Meeting Intelligence — AI Engineer Technical Assessment

A web application that takes client meeting transcripts and turns them into structured project scopes, actionable tasks, sprint plans, and Jira issues — with a human reviewing and approving every stage.

## Setup

```bash
# 1. Clone / navigate to the project folder
cd meeting-intelligence

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 5. Run the app
streamlit run app.py
```

The app opens at http://localhost:8501.

## How Each Stage Works

### Stage 1 — Transcript Analysis
Upload or paste a meeting transcript. The AI extracts structured fields (project name, client, modules, requirements, integrations, constraints, assumptions, unknowns) with a confidence indicator per field. Type corrections in plain English and the AI updates the extraction. Approve to advance.

### Stage 2 — Clarification Q&A
The AI generates targeted questions citing specific parts of the transcript. Answer them in the app; the AI follows up if an answer opens a new question or marks it resolved. You can also ask your own questions. Click "Done" when satisfied.

### Stage 3 — Scope of Work
The AI writes a full SoW (executive summary, in-scope / out-of-scope, modules, integrations, constraints, open items, timeline). Give free-text feedback; the AI revises and shows a changelog. Repeat until happy, then approve. Download the SoW as Markdown.

### Stage 4 — Sprint Planning
The AI breaks the SoW into tasks with Fibonacci story points and organises them into 2-week sprints (max 40 points each). Move tasks between sprints using the dropdowns, then approve.

### Stage 5 — Jira Sync
Enter your Jira credentials (domain, email, API token, project key). The app tests the connection, shows a preview of every Epic / Issue / Sprint that will be created, and lets you confirm each batch. Live progress is shown, and every created issue links back to Jira.

## Jira Configuration Steps

1. Log in to Jira Cloud at https://yourcompany.atlassian.net
2. Generate an API token at https://id.atlassian.com/manage-api-tokens
3. In Stage 5, fill in:
   - **Domain**: `yourcompany.atlassian.net`
   - **Email**: the email you log in with
   - **API Token**: the token you just generated
   - **Project Key**: e.g. `MIM` (visible in your Jira project URL)
4. Click **Test Connection** before syncing

The app uses the Jira Cloud REST API v3 and Agile API v1. A free Jira account is sufficient.

## Design Decisions

- **Streamlit** for the full-stack UI — fast to develop, clean for a demo flow
- **SQLite** for persistence — page refreshes never lose progress; each project is fully isolated
- **GPT-4o** for all AI stages — structured JSON output with a fallback parse loop
- **Modular stage files** — each stage is self-contained; easy to extend or replace
- **Human-in-the-loop gates** — nothing advances without an explicit approval click

## Known Limitations

- Jira sprint creation requires a board attached to the project key (scrum board, not kanban)
- Story point field defaults to `customfield_10016` (standard for Jira Cloud next-gen); classic projects may differ
- Superannuation / data-scraping integrations mentioned in transcripts are flagged as unknowns, not wired to live APIs
- The app is single-user; concurrent project editing from multiple browsers is not handled

## Project Structure

```
meeting-intelligence/
├── app.py              # Streamlit entry point
├── requirements.txt
├── .env.example
├── README.md
└── src/
    ├── db.py           # SQLite helpers
    ├── ai.py           # OpenAI pipeline (all 5 stages)
    ├── jira.py         # Jira REST + Agile API client
    └── ui/
        ├── stage1.py   # Transcript analysis UI
        ├── stage2.py   # Clarification Q&A UI
        ├── stage3.py   # Scope of Work UI
        ├── stage4.py   # Sprint planning UI
        └── stage5.py   # Jira sync UI
```
