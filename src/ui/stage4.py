import streamlit as st
from src import ai, db

PRI = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
TYPE_ICON = {"Story": "📖", "Task": "✅", "Epic": "⚡"}


def render(project):
    pid = project["id"]
    st.subheader("Stage 4 — Sprint Planning")

    if not project.get("stage3_approved"):
        st.warning("Approve Stage 3 first.")
        return

    plan = project.get("stage4_data", {})
    approved = project.get("stage4_approved", 0)

    if not plan or not plan.get("tasks"):
        if st.button("📅 Generate Sprint Plan", type="primary"):
            with st.spinner("Planning sprints…"):
                try:
                    plan = ai.stage4_generate_plan(
                        project.get("stage3_sow", ""),
                        project.get("stage1_data", {}),
                    )
                    db.update_project(pid, stage4_data=plan)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        return

    tasks = plan.get("tasks", [])
    sprints = plan.get("sprints", [])
    sprint_names = [s["name"] for s in sprints]

    st.markdown("### Sprint Overview")
    for s in sprints:
        pts = s.get("story_points", 0)
        over = s.get("over_capacity") or pts > 40
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"**{s['name']}** — _{s.get('goal', '')}_")
        with c2:
            color = "red" if over else "green"
            st.markdown(f'<span style="color:{color};font-weight:700">{pts} pts</span>', unsafe_allow_html=True)
        with c3:
            if over:
                st.warning("⚠️ Over limit")

    st.divider()
    st.markdown("### Tasks")
    st.caption("Move tasks between sprints using the dropdowns below.")

    changed = False
    for i, task in enumerate(tasks):
        pts = task.get("story_points", 0)
        icon = TYPE_ICON.get(task.get("type", "Story"), "📖")
        pri = PRI.get(task.get("priority", "Medium"), "")
        header = f"{icon} {pri} [{task['id']}] {task['title']} ({pts} pts)"

        with st.expander(header, expanded=False):
            st.markdown(task.get("description", ""))
            st.markdown(
                f"**Module:** {task.get('module', '—')} | "
                f"**Type:** {task.get('type', '—')} | "
                f"**Priority:** {task.get('priority', '—')} | "
                f"**Points:** {pts}"
            )
            if task.get("dependencies"):
                st.markdown(f"**Depends on:** {', '.join(task['dependencies'])}")
            if task.get("acceptance_criteria"):
                st.markdown("**Acceptance Criteria:**")
                for ac in task["acceptance_criteria"]:
                    st.markdown(f"- {ac}")

            if not approved and sprint_names:
                cur = task.get("sprint", sprint_names[0])
                idx_default = sprint_names.index(cur) if cur in sprint_names else 0
                picked = st.selectbox("Sprint", sprint_names, index=idx_default, key=f"sp_{pid}_{i}")
                if picked != task.get("sprint"):
                    tasks[i]["sprint"] = picked
                    changed = True

    if changed:
        for s in sprints:
            s["task_ids"] = [t["id"] for t in tasks if t.get("sprint") == s["name"]]
            s["story_points"] = sum(t.get("story_points", 0) for t in tasks if t.get("sprint") == s["name"])
            s["over_capacity"] = s["story_points"] > 40
        plan["tasks"] = tasks
        plan["sprints"] = sprints
        db.update_project(pid, stage4_data=plan)
        st.rerun()

    if not approved:
        st.divider()
        if st.button("✅ Approve Sprint Plan — go to Stage 5", type="primary"):
            db.update_project(pid, stage4_approved=1, current_stage=5)
            st.rerun()

    if approved:
        st.success("✅ Stage 4 approved.")
