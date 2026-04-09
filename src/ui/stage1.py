import streamlit as st
from src import ai, db

CONF_BADGE = {"high": "🟢 High", "medium": "🟡 Medium", "low": "🔴 Low"}
CONF_COLOR = {"high": "green", "medium": "orange", "low": "red"}


def conf_html(conf):
    color = CONF_COLOR.get(conf, "grey")
    label = CONF_BADGE.get(conf, conf)
    return f'<span style="color:{color};font-weight:600">{label}</span>'


def scalar_row(label, field):
    if not isinstance(field, dict):
        st.markdown(f"**{label}:** {field or '—'}")
        return
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**{label}:** {field.get('value') or '—'}")
        if field.get("note"):
            st.caption(field["note"])
    with col2:
        st.markdown(conf_html(field.get("confidence", "low")), unsafe_allow_html=True)


def list_section(title, items, primary_key, extra_fields):
    if not items:
        st.info(f"No {title.lower()} found.")
        return
    st.markdown(f"**{title}** ({len(items)})")
    for i, item in enumerate(items):
        conf = item.get("confidence", "medium")
        header = f"{CONF_BADGE.get(conf, '')}  {item.get(primary_key, f'Item {i+1}')}"
        with st.expander(header, expanded=False):
            for key, label in extra_fields:
                val = item.get(key)
                if val:
                    st.markdown(f"**{label}:** {val}")
            st.markdown(conf_html(conf), unsafe_allow_html=True)


def render(project):
    pid = project["id"]
    st.subheader("Stage 1 — Transcript Analysis")

    approved = project.get("stage1_approved")

    if not approved:
        transcript = st.text_area(
            "Paste transcript",
            value=project.get("transcript", ""),
            height=200,
            placeholder="Paste the full meeting transcript here…",
        )
        uploaded = st.file_uploader("Or upload a .txt file", type=["txt"])
        if uploaded:
            transcript = uploaded.read().decode("utf-8", errors="replace")
            st.success("File loaded.")

        if st.button("💾 Save Transcript"):
            db.update_project(pid, transcript=transcript)
            st.rerun()

    transcript = project.get("transcript", "")
    data = project.get("stage1_data", {})

    if transcript and not data and not approved:
        if st.button("🔍 Analyze Transcript", type="primary"):
            with st.spinner("Analyzing… this can take 20–40 seconds"):
                try:
                    result = ai.stage1_extract(transcript)
                    db.update_project(pid, stage1_data=result)
                    st.rerun()
                except Exception as e:
                    st.error(f"AI error: {e}")

    if data:
        st.divider()
        st.markdown("### Extracted Information")

        for key, label in [("project_name", "Project"), ("client_name", "Client"), ("vendor_name", "Vendor")]:
            scalar_row(label, data.get(key, {}))

        st.divider()
        list_section("Modules", data.get("modules", []), "name",
                     [("description", "Description"), ("priority", "Priority"), ("deadline", "Deadline")])
        list_section("Requirements", data.get("requirements", []), "description",
                     [("module", "Module"), ("type", "Type")])
        list_section("Integrations", data.get("integrations", []), "name",
                     [("description", "Description")])
        list_section("Constraints", data.get("constraints", []), "description", [])
        list_section("Assumptions", data.get("assumptions", []), "description", [])
        list_section("Unknowns / Open Items", data.get("unknowns", []), "description", [])

        if not approved:
            st.divider()
            st.markdown("#### Apply a Correction")
            correction = st.text_input(
                "Type in plain English",
                placeholder='e.g. "The vendor name is Acme, not Software Co"',
                key="s1_correction",
            )
            if st.button("✏️ Apply Correction") and correction.strip():
                with st.spinner("Updating…"):
                    try:
                        updated = ai.stage1_correct(data, correction.strip())
                        db.update_project(pid, stage1_data=updated)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

            st.divider()
            if st.button("✅ Approve & go to Stage 2", type="primary"):
                db.update_project(pid, stage1_approved=1, current_stage=2)
                st.rerun()

    elif not transcript:
        st.info("Paste a transcript above and click **Analyze Transcript** to begin.")

    if approved:
        st.success("✅ Stage 1 approved.")
