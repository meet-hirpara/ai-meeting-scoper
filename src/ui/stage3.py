import streamlit as st
from src import ai, db


def render(project):
    pid = project["id"]
    st.subheader("Stage 3 — Scope of Work")

    if not project.get("stage2_approved"):
        st.warning("Approve Stage 2 first.")
        return

    sow = project.get("stage3_sow", "")
    changelog = project.get("stage3_changelog", [])
    feedback_count = project.get("stage3_feedback_count", 0)
    approved = project.get("stage3_approved", 0)

    if not sow:
        if st.button("📝 Generate Scope of Work", type="primary"):
            with st.spinner("Writing SoW… (30–60 seconds)"):
                try:
                    sow = ai.stage3_generate_sow(
                        project.get("transcript", ""),
                        project.get("stage1_data", {}),
                        project.get("stage2_data", []),
                    )
                    db.update_project(pid, stage3_sow=sow)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        return

    st.markdown(sow)

    if changelog:
        with st.expander(f"📋 Changelog ({len(changelog)} revisions)", expanded=False):
            for i, changes in enumerate(changelog, 1):
                st.markdown(f"**Revision {i}:**")
                items = changes if isinstance(changes, list) else [changes]
                for c in items:
                    st.markdown(f"- {c}")

    if not approved:
        st.divider()
        feedback = st.text_area(
            "Feedback for revision",
            height=100,
            placeholder="e.g. Expand the integrations section. Remove mention of Salesforce — it's out of scope.",
            key=f"fb_{pid}",
        )
        if st.button("🔄 Revise") and feedback.strip():
            with st.spinner("Revising…"):
                try:
                    result = ai.stage3_revise_sow(sow, feedback.strip())
                    new_sow = result.get("revised_sow", sow)
                    new_changes = result.get("changelog", [])
                    db.update_project(
                        pid,
                        stage3_sow=new_sow,
                        stage3_changelog=changelog + [new_changes],
                        stage3_feedback_count=feedback_count + 1,
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"Revision failed: {e}")

        st.download_button("⬇️ Download (.md)", data=sow.encode(), file_name="scope_of_work.md", mime="text/markdown")

        st.divider()
        if feedback_count == 0:
            st.info("Give at least one round of feedback before approving.")
        else:
            if st.button("✅ Approve SoW — go to Stage 4", type="primary"):
                db.update_project(pid, stage3_approved=1, current_stage=4)
                st.rerun()

    if approved:
        st.success("✅ Stage 3 approved.")
        st.download_button("⬇️ Download (.md)", data=sow.encode(), file_name="scope_of_work.md", mime="text/markdown")
