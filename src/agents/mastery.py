"""
agents/mastery.py — MasteryAgent (replaces reveal.py).

Triggered when the student types /mastery (unlocks after turn 3).

Generates a structured post-session summary covering:
  1. The complete direct answer
  2. The student's attempt journey
  3. The clinical scenario + model answer
  4. A clinical pearl / mnemonic
  5. Suggested next topics
"""

from src.llm import llm_chat

_MASTERY_SYSTEM = """\
You are an expert OT educator writing a post-session mastery summary.

Write clearly under EXACTLY these 5 section headers (use them verbatim):

## Answer
State the complete, textbook-grounded answer to the student's question.
Be thorough. Ground every claim in the retrieved context provided.

## Your Journey
Summarise the student's attempts across the session.
Acknowledge what they got right. Name any specific mistakes and explain corrections.
Be warm and constructive.

## Clinical Application
Present the clinical scenario from the session and explain what a model answer looks like —
e.g. how the lesion presents clinically and what OT interventions would follow.

## Clinical Pearl
Give one memorable mnemonic or high-yield fact the student can take away.

## What to Study Next
If the student made mistakes or is weak on related topics, suggest 1-2 specific topics to review.

Tone: warm mentor. Ground the Answer strictly in provided context — do not invent facts.\
"""


def run_mastery(session) -> str:
    """
    MasteryAgent — generates the full post-session summary.

    Args:
        session: QuestionSession with all attempt logs and private knowledge

    Returns:
        A formatted mastery summary string.
    """
    attempt_lines = []
    for i, att in enumerate(session.attempts, 1):
        quality  = att.get("answer_quality", "unanswered")
        score    = att.get("proximity_score", 0)
        summary  = att.get("attempt_summary") or "(no attempt — student asked a question)"
        attempt_lines.append(
            f"  Turn {att.get('turn', i)} [{att.get('phase', '?')}] "
            f"quality={quality} score={score}/100\n"
            f"  Student: {att.get('student_message', '')[:200]}\n"
            f"  Summary: {summary}"
        )

    mistake_lines = []
    for m in session.mistakes:
        mistake_lines.append(f"  - [{m.get('topic', '?')}] {m.get('excerpt', '')}")

    prompt = "\n".join([
        "ORIGINAL QUESTION:",
        session.original_question,
        "",
        "RETRIEVED TEXTBOOK CONTEXT (ground the Answer section here):",
        session.retrieved_context or "No context available.",
        "",
        "DIRECT ANSWER (already computed — use as primary source for the Answer section):",
        session.direct_answer or "Not available.",
        "",
        "CLINICAL SCENARIO:",
        session.clinical_scenario or "Not available.",
        "",
        "USEFUL INFO / MNEMONIC:",
        session.useful_info or "Not available.",
        "",
        "STUDENT ATTEMPT LOG:",
        *(attempt_lines if attempt_lines else ["  No attempts recorded."]),
        "",
        "STUDENT MISTAKES:",
        *(mistake_lines if mistake_lines else ["  No mistakes recorded — great work!"]),
        "",
        "Write the full mastery summary now.",
    ])

    return llm_chat(_MASTERY_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=1024)
