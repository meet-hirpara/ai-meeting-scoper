import streamlit as st
from src import db
from src.jira import JiraClient


def render(project):
    pid = project["id"]
    st.subheader("Stage 5 — Jira Sync")

    if not project.get("stage4_approved"):
        st.warning("Approve Stage 4 first.")
        return

    plan = project.get("stage4_data", {})
    tasks = plan.get("tasks", [])
    sprints = plan.get("sprints", [])
    cfg = project.get("stage5_jira_config", {})
    results = project.get("stage5_results", {})
    approved = project.get("stage5_approved", 0)

    st.markdown("### Jira Configuration")
    st.caption("Get your API token at [id.atlassian.com/manage-api-tokens](https://id.atlassian.com/manage-api-tokens)")

    with st.form("jira_form"):
        domain = st.text_input("Domain", value=cfg.get("domain", ""), placeholder="yourcompany.atlassian.net")
        email = st.text_input("Email", value=cfg.get("email", ""))
        token = st.text_input("API Token", value=cfg.get("token", ""), type="password")
        pkey = st.text_input("Project Key", value=cfg.get("project_key", ""), placeholder="MIM")
        submitted = st.form_submit_button("💾 Save & Test Connection")

    if submitted:
        if not all([domain, email, token, pkey]):
            st.error("Fill in all fields.")
        else:
            new_cfg = {"domain": domain.strip(), "email": email.strip(), "token": token.strip(), "project_key": pkey.strip().upper()}
            db.update_project(pid, stage5_jira_config=new_cfg)
            with st.spinner("Testing…"):
                test = JiraClient(**new_cfg).test_connection()
            if test["ok"]:
                st.success(f"✅ {test['message']}")
            else:
                st.error(f"❌ {test['message']}")
            st.rerun()

    cfg = project.get("stage5_jira_config", {})
    if not cfg.get("domain"):
        st.info("Enter Jira credentials above to continue.")
        return

    st.divider()
    st.markdown("### Preview")

    modules = list({t["module"] for t in tasks if t.get("module")})
    st.markdown(f"**Epics ({len(modules)}):** " + ", ".join(f"`{m}`" for m in modules))
    st.markdown(f"**Issues:** {len(tasks)} tasks")
    st.markdown(f"**Sprints:** {len(sprints)}")
    for s in sprints:
        st.markdown(f"  - {s['name']} — {s.get('story_points', '?')} pts")

    if not approved:
        st.divider()
        if st.button("🚀 Create Everything in Jira", type="primary"):
            _run_sync(pid, cfg, plan, tasks, sprints)

    if results:
        _show_results(results, cfg)

    if approved:
        st.success("✅ All done — everything is in Jira.")


def _run_sync(pid, cfg, plan, tasks, sprints):
    client = JiraClient(**cfg)

    epics_ph = st.empty()
    issues_ph = st.empty()
    sprints_ph = st.empty()

    epic_results, issue_results, sprint_results, errors = [], [], [], []

    try:
        for event in client.sync_plan(plan):
            phase = event.get("phase")

            if phase == "Epics":
                epics_ph.progress(event["done"] / event["total"], text=f"Creating Epics… {event['done']}/{event['total']}")
                if event["error"]:
                    errors.append(f"Epic: {event['error']}")
                else:
                    epic_results.append({"key": event["key"], "url": event["url"]})

            elif phase == "Issues":
                issues_ph.progress(event["done"] / event["total"], text=f"Creating Issues… {event['done']}/{event['total']}")
                if event["error"]:
                    errors.append(f"Issue: {event['error']}")
                else:
                    issue_results.append({"key": event["key"], "url": event["url"]})

            elif phase == "Sprints":
                sprints_ph.progress(event["done"] / event["total"], text=f"Creating Sprints… {event['done']}/{event['total']}")
                if event["error"]:
                    errors.append(f"Sprint '{event['key']}': {event['error']}")
                else:
                    sprint_results.append({"name": event["key"]})

            elif phase == "done":
                st.success("✅ Sync complete!")
                db.update_project(pid, stage5_results={"epics": epic_results, "issues": issue_results, "sprints": sprint_results, "errors": errors}, stage5_approved=1)
                st.rerun()

    except Exception as e:
        st.error(f"Sync failed: {e}")


def _show_results(results, cfg):
    st.divider()
    st.markdown("### Results")
    base = f"https://{cfg.get('domain', '')}"

    st.markdown(f"**Epics ({len(results.get('epics', []))}):**")
    for e in results.get("epics", []):
        st.markdown(f"- [{e['key']}]({e.get('url') or base + '/browse/' + e['key']})")

    st.markdown(f"**Issues ({len(results.get('issues', []))}):**")
    cols = st.columns(4)
    for i, iss in enumerate(results.get("issues", [])):
        with cols[i % 4]:
            st.markdown(f"[{iss['key']}]({iss.get('url') or base + '/browse/' + iss['key']})")

    st.markdown(f"**Sprints ({len(results.get('sprints', []))}):**")
    for s in results.get("sprints", []):
        st.markdown(f"- {s['name']}")

    for err in results.get("errors", []):
        st.warning(err)
