"""
agents/analyzer.py — silent analysis agent; outputs structured JSON, never talks to student.
"""

import json
from src.llm import llm_chat

ANALYZER_SYSTEM_PROMPT = """\
You are a silent knowledge-analysis agent for a Socratic OT tutoring system.
Given a student's message, the RAG context, and the conversation history FOR THE CURRENT QUESTION SESSION,
you produce a structured JSON analysis used by the Manager and Tutor agents.

You NEVER speak to the student. Output ONLY valid JSON — no preamble, no markdown fences.

Required schema:
{
  "direct_answer": "The complete, accurate answer to the student's ORIGINAL question, grounded strictly in the provided context. PRIVATE — never shown to student until /reveal.",

  "clinical_scenario": "A 1-2 sentence clinical application scenario related to this topic.",

  "related_questions": [
    "An easy Socratic opening question nudging toward the answer",
    "A medium question exploring a connected anatomical or functional concept",
    "A harder clinical application question"
  ],

  "student_answer_quality": "correct" | "partial" | "wrong" | "unanswered",

  "proximity_score": 0-100,

  "useful_info": "One sentence of additional clinical context or mnemonic grounded in the provided context.",

  "topic_label": "2-5 word lowercase label for this topic. null if unclear.",

  "attempt_summary": "1-2 sentence summary of what the student got right/wrong. null if they only asked a question.",

  "mistake_excerpt": "The specific wrong claim the student made, verbatim (max 80 chars). null if no mistake."
}

Rules:
- direct_answer: always ground in CONTEXT. If insufficient write "Insufficient context — topic not covered in retrieved passages."
- related_questions: exactly 3, ordered easy → hard.
- proximity_score: 0 = completely wrong/no attempt, 50 = partial, 100 = fully correct.
- student_answer_quality: "unanswered" if student only asked a question.
- attempt_summary and mistake_excerpt: null when quality is "unanswered".
"""

_FALLBACK = {
    "direct_answer": "Parse error — could not extract answer.",
    "clinical_scenario": "A patient presents with peripheral nerve injury. Describe the functional deficit.",
    "related_questions": [
        "What do you already know about this structure?",
        "Where in the body does this structure originate?",
        "What happens clinically when this structure is damaged?",
    ],
    "student_answer_quality": "unanswered",
    "proximity_score": 0,
    "useful_info": "",
    "topic_label": None,
    "attempt_summary": None,
    "mistake_excerpt": None,
}


def run_analyzer(
    student_message: str,
    context: str,
    question_session_history: list,
    original_question: str,
) -> dict:
    history_snippet = ""
    if question_session_history:
        recent = question_session_history[-6:]
        history_snippet = "\n".join(
            f"{t['role'].upper()}: {t['content'][:300]}" for t in recent
        )

    prompt = (
        f"ORIGINAL QUESTION (anchor — what the student is trying to learn):\n{original_question}\n\n"
        f"CONVERSATION HISTORY FOR THIS QUESTION SESSION (last 6 turns):\n"
        f"{history_snippet or 'No history yet — this is the first turn.'}\n\n"
        f"STUDENT'S LATEST MESSAGE:\n{student_message}\n\n"
        f"RETRIEVED TEXTBOOK CONTEXT:\n{context or 'No context retrieved.'}\n\n"
        "Produce the JSON analysis now."
    )

    raw = llm_chat(ANALYZER_SYSTEM_PROMPT, [{"role": "user", "content": prompt}])

    clean = raw.strip()
    if clean.startswith("```"):
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip().rstrip("`").strip()

    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        print(f"[Analyzer] JSON parse error. Raw:\n{raw[:400]}")
        return _FALLBACK.copy()
