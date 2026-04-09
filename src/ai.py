import json
import os
import re

from openai import OpenAI

_client = None
_model = None


def _setup():
    global _client, _model
    oai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gem_key = os.getenv("GEMINI_API_KEY", "").strip()

    if oai_key and not oai_key.startswith("sk-..."):
        _model = os.getenv("OPENAI_MODEL", "gpt-4o")
        _client = OpenAI(api_key=oai_key)
    elif gem_key:
        # Gemini exposes an OpenAI-compatible endpoint so we can reuse the same SDK
        _model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        _client = OpenAI(
            api_key=gem_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
    else:
        raise RuntimeError("No AI key found — set OPENAI_API_KEY or GEMINI_API_KEY in .env")


def get_client():
    if _client is None:
        _setup()
    return _client


def get_model():
    if _model is None:
        _setup()
    return _model


def _chat(system, user, json_mode=True):
    kwargs = {
        "model": get_model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = get_client().chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _parse(text):
    text = text.strip()
    # strip markdown code fences if the model wraps output in them
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ── Stage 1 ─────────────────────────────────────────────────────────────────

_S1_SYSTEM = """You are a senior business analyst. Extract ALL structured information from client meeting transcripts.

Confidence levels:
- "high": explicitly stated in the transcript
- "medium": mentioned but needs interpretation
- "low": inferred or implied

Extract more rather than less. Be thorough."""

_S1_SCHEMA = """{
  "project_name":  {"value": "...", "confidence": "high|medium|low", "note": "..."},
  "client_name":   {"value": "...", "confidence": "high|medium|low", "note": "..."},
  "vendor_name":   {"value": "...", "confidence": "high|medium|low", "note": "..."},
  "modules": [
    {"name": "...", "description": "...", "priority": "High|Medium|Low", "deadline": "... or null", "confidence": "high|medium|low"}
  ],
  "requirements": [
    {"description": "...", "module": "...", "type": "Functional|Non-Functional|Integration", "confidence": "high|medium|low"}
  ],
  "integrations": [
    {"name": "...", "description": "...", "confidence": "high|medium|low"}
  ],
  "constraints":  [{"description": "...", "confidence": "high|medium|low"}],
  "assumptions":  [{"description": "...", "confidence": "high|medium|low"}],
  "unknowns":     [{"description": "...", "confidence": "high|medium|low"}]
}"""


def stage1_extract(transcript):
    prompt = (
        f"Analyze this meeting transcript and return ONLY valid JSON matching this schema:\n\n"
        f"{_S1_SCHEMA}\n\nTRANSCRIPT:\n{transcript}"
    )
    return _parse(_chat(_S1_SYSTEM, prompt))


def stage1_correct(current_data, correction):
    prompt = (
        f"Apply this plain-language correction to the extracted data and return the updated JSON "
        f"with the same schema.\n\n"
        f"CURRENT DATA:\n{json.dumps(current_data, indent=2)}\n\n"
        f"CORRECTION: {correction}"
    )
    return _parse(_chat(_S1_SYSTEM, prompt))


# ── Stage 2 ─────────────────────────────────────────────────────────────────

_S2_SYSTEM = """You are a business analyst generating clarification questions for a client project.
Every question must cite a specific part of the transcript explaining why it needs answering.
No generic filler questions."""


def stage2_generate_questions(transcript, stage1_data):
    prompt = (
        "Generate at least 5 targeted clarification questions.\n"
        "Each question MUST reference something specific from the transcript.\n\n"
        'Return JSON with key "questions" containing:\n'
        '[{"id": "q1", "question": "...", "reason": "Citing: \\"[quote]\\" — because ...", '
        '"answer": null, "follow_up": null, "status": "pending"}]\n\n'
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"EXTRACTED DATA:\n{json.dumps(stage1_data, indent=2)}"
    )
    data = _parse(_chat(_S2_SYSTEM, prompt))
    if isinstance(data, dict):
        # handle different wrapper keys the model might use
        for key in ("questions", "items", "clarifications"):
            if key in data:
                return data[key]
        # last resort: grab first list value
        for v in data.values():
            if isinstance(v, list):
                return v
    return data


def stage2_process_answer(question, reason, answer):
    prompt = (
        f"Question: {question}\n"
        f"Why asked: {reason}\n"
        f"Answer: {answer}\n\n"
        "Does this answer resolve the topic, or does it open a follow-up question?\n"
        'Return JSON: {"action": "follow_up", "follow_up_question": "..."} or {"action": "resolved"}'
    )
    return _parse(_chat(_S2_SYSTEM, prompt))


def stage2_answer_user_question(transcript, stage1_data, questions, user_q):
    ctx = (
        f"Transcript (first 3000 chars):\n{transcript[:3000]}\n\n"
        f"Extracted data:\n{json.dumps(stage1_data, indent=2)}\n\n"
        f"Q&A so far:\n{json.dumps(questions, indent=2)}"
    )
    return _chat(_S2_SYSTEM, f"Context:\n{ctx}\n\nQuestion: {user_q}", json_mode=False)


# ── Stage 3 ─────────────────────────────────────────────────────────────────

_S3_SYSTEM = "You are a senior technical writer producing professional Scope of Work documents."

_SOW_SECTIONS = """
1. Executive Summary
2. In-Scope Items (by module)
3. Out-of-Scope Items (explicit)
4. Modules and Deliverables (features + acceptance criteria per module)
5. Integrations (name, purpose, type, data flow)
6. Constraints and Assumptions
7. Open Items
8. Timeline Overview
""".strip()


def stage3_generate_sow(transcript, stage1_data, stage2_questions):
    answered = [q for q in stage2_questions if q.get("answer")]
    qa_text = "\n".join(f"Q: {q['question']}\nA: {q['answer']}" for q in answered) or "None."
    prompt = (
        f"Write a complete Scope of Work in Markdown with these sections:\n{_SOW_SECTIONS}\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        f"EXTRACTED DATA:\n{json.dumps(stage1_data, indent=2)}\n\n"
        f"CLARIFICATIONS:\n{qa_text}"
    )
    return _chat(_S3_SYSTEM, prompt, json_mode=False)


def stage3_revise_sow(current_sow, feedback):
    prompt = (
        f"Revise this Scope of Work based on the feedback below.\n\n"
        f"CURRENT SOW:\n{current_sow}\n\n"
        f"FEEDBACK: {feedback}\n\n"
        'Return JSON: {"revised_sow": "...", "changelog": ["change 1", "change 2"]}'
    )
    return _parse(_chat(_S3_SYSTEM, prompt))


# ── Stage 4 ─────────────────────────────────────────────────────────────────

_S4_SYSTEM = """You are an agile delivery expert creating sprint plans from Scope of Work documents.

Rules:
- 2-week sprints, max 40 story points per sprint
- Fibonacci story points only: 1, 2, 3, 5, 8, 13
- Sprint names must reflect their goal e.g. "Sprint 1 — Core Auth"
- Respect task dependencies (no task can be in an earlier sprint than its dependency)
- Each task needs at least 2 acceptance criteria
- Set over_capacity: true if sprint exceeds 40 points"""


def stage4_generate_plan(sow, stage1_data):
    modules = stage1_data.get("modules", [])
    prompt = (
        "Create a full sprint plan. Return ONLY valid JSON:\n\n"
        '{"tasks": [{"id": "T001", "title": "...", "description": "2-3 sentences", '
        '"module": "...", "type": "Story|Task|Epic", "priority": "High|Medium|Low", '
        '"story_points": 1|2|3|5|8|13, "dependencies": ["T002"], '
        '"acceptance_criteria": ["...", "..."], "sprint": "Sprint 1 — Goal"}], '
        '"sprints": [{"name": "Sprint 1 — Goal", "goal": "...", "duration": "2 weeks", '
        '"story_points": 35, "task_ids": ["T001"], "over_capacity": false}]}\n\n'
        f"SCOPE OF WORK:\n{sow}\n\n"
        f"MODULES:\n{json.dumps(modules, indent=2)}"
    )
    return _parse(_chat(_S4_SYSTEM, prompt))
