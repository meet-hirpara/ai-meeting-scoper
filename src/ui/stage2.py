import streamlit as st
from src import ai, db

STATUS_ICON = {"pending": "⏳", "answered": "💬", "resolved": "✅", "skipped": "⏭️"}


def render(project):
    pid = project["id"]
    st.subheader("Stage 2 — Clarification Q&A")

    if not project.get("stage1_approved"):
        st.warning("Approve Stage 1 first.")
        return

    questions = project.get("stage2_data", [])
    approved = project.get("stage2_approved", 0)

    if not questions:
        if st.button("🤔 Generate Questions", type="primary"):
            with st.spinner("Generating targeted questions…"):
                try:
                    qs = ai.stage2_generate_questions(
                        project.get("transcript", ""),
                        project.get("stage1_data", {}),
                    )
                    for i, q in enumerate(qs):
                        q.setdefault("id", f"q{i+1}")
                        q.setdefault("answer", None)
                        q.setdefault("follow_up", None)
                        q.setdefault("status", "pending")
                    db.update_project(pid, stage2_data=qs)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        return

    pending_count = sum(1 for q in questions if q.get("status") in ("pending", "answered"))
    resolved_count = len(questions) - pending_count
    st.markdown(f"{len(questions)} questions — {resolved_count} resolved, {pending_count} remaining")

    changed = False
    for idx, q in enumerate(questions):
        status = q.get("status", "pending")
        icon = STATUS_ICON.get(status, "❓")
        preview = q["question"][:80] + ("…" if len(q["question"]) > 80 else "")

        with st.expander(f"{icon} Q{idx+1}: {preview}", expanded=(status == "pending" and not approved)):
            st.markdown(f"**{q['question']}**")
            st.caption(f"Why asked: {q.get('reason', '')}")

            if q.get("follow_up"):
                st.info(f"Follow-up: {q['follow_up']}")

            if status in ("pending", "answered") and not approved:
                answer = st.text_area("Your answer", value=q.get("answer") or "", key=f"ans_{pid}_{idx}", height=80)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Submit", key=f"sub_{pid}_{idx}"):
                        with st.spinner("Processing…"):
                            try:
                                res = ai.stage2_process_answer(q["question"], q.get("reason", ""), answer)
                                q["answer"] = answer
                                if res.get("action") == "follow_up":
                                    q["follow_up"] = res.get("follow_up_question")
                                    q["status"] = "answered"
                                else:
                                    q["status"] = "resolved"
                                changed = True
                            except Exception as e:
                                st.error(f"Error: {e}")
                with col2:
                    reason = st.text_input("Skip reason", key=f"skipr_{pid}_{idx}")
                    if st.button("Skip ⏭️", key=f"skip_{pid}_{idx}"):
                        q["answer"] = f"[SKIPPED] {reason}"
                        q["status"] = "skipped"
                        changed = True

            elif q.get("answer"):
                st.markdown(f"**Answer:** {q['answer']}")
                st.caption(f"Status: {icon} {status}")

    if changed:
        db.update_project(pid, stage2_data=questions)
        st.rerun()

    if not approved:
        st.divider()
        st.markdown("#### Ask your own question")
        user_q = st.text_input("Question about scope, sprints, anything…", key=f"uq_{pid}")
        if st.button("Ask", key=f"ask_{pid}") and user_q.strip():
            with st.spinner("Thinking…"):
                try:
                    ans = ai.stage2_answer_user_question(
                        project.get("transcript", ""),
                        project.get("stage1_data", {}),
                        questions,
                        user_q.strip(),
                    )
                    uqa = project.get("stage2_user_qa", [])
                    uqa.append({"question": user_q.strip(), "answer": ans})
                    db.update_project(pid, stage2_user_qa=uqa)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    uqa = project.get("stage2_user_qa", [])
    if uqa:
        st.markdown("**Your Q&A:**")
        for item in uqa:
            with st.expander(f"💡 {item['question'][:80]}", expanded=False):
                st.markdown(item["answer"])

    if not approved:
        st.divider()
        if st.button("✅ Done — go to Stage 3", type="primary"):
            db.update_project(pid, stage2_approved=1, current_stage=3)
            st.rerun()

    if approved:
        st.success("✅ Stage 2 approved.")
