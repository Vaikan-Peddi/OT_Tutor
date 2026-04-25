"""
agents/reveal.py — RevealAgent.

Spec requirement (Task 3 — Synthesis & Assessment):
  "The agent compares the student's reasoning against the gold-standard textbook data
   and provides a mastery summary."

Triggered only when the student types /reveal (after turn threshold).
Generates a structured, LLM-written mastery summary — NOT a raw string-format dump.
The summary covers:
  1. The complete, grounded direct answer
  2. The student's journey (what they got right/wrong across attempts)
  3. The clinical scenario + what a correct response looks like
  4. A clinical pearl / mnemonic to remember the concept
  5. Suggested next steps if weak topics remain
"""

from src.llm import llm_chat

REVEAL_SYSTEM_PROMPT = """\
You are an expert OT educator writing a post-session mastery summary for a student \
who has just completed a Socratic tutoring session.

Your summary must cover ALL of the following sections in order:

1. DIRECT ANSWER — The complete, textbook-grounded answer to the student's original question. \
   Be thorough and accurate. Ground every claim in the retrieved context provided.

2. YOUR JOURNEY — Summarise the student's attempts across the session. \
   Acknowledge what they got right. Name any specific mistakes they made and explain the correction. \
   Be warm and constructive, not critical.

3. CLINICAL APPLICATION — Present the clinical scenario from the session and explain \
   what a model answer looks like (e.g., how the nerve lesion presents clinically, \
   what OT interventions would follow).

4. CLINICAL PEARL — Give one memorable mnemonic or high-yield fact the student can take away.

5. WHAT TO STUDY NEXT — If the student made mistakes or is weak on related topics, \
   suggest 1-2 specific topics to review next.

Write in a warm, mentor-like tone. Use clear section headers. \
Ground the DIRECT ANSWER strictly in the provided context — do not hallucinate facts.
"""


def run_reveal(session) -> str:
    """
    RevealAgent — generates a full mastery summary for the completed session.

    Args:
        session: QuestionSession with all attempt logs and private knowledge

    Returns:
        A formatted mastery summary string.
    """
    # Build attempt log for the LLM
    attempt_lines = []
    for i, att in enumerate(session.attempts, 1):
        quality = att.get("answer_quality", "unanswered")
        score   = att.get("proximity_score", 0)
        summary = att.get("attempt_summary") or "(no attempt — student asked a question)"
        attempt_lines.append(
            f"  Turn {att.get('turn', i)} [{att.get('phase', '?')}] "
            f"quality={quality} score={score}/100\n"
            f"  Student: {att.get('student_message', '')[:200]}\n"
            f"  Summary: {summary}"
        )

    mistake_lines = []
    for m in session.mistakes:
        mistake_lines.append(f"  - [{m.get('topic', '?')}] {m.get('excerpt', '')}")

    prompt_parts = [
        "ORIGINAL QUESTION:",
        session.original_question,
        "",
        "RETRIEVED TEXTBOOK CONTEXT (ground the direct answer here):",
        session.retrieved_context or "No context available.",
        "",
        "PRIVATE DIRECT ANSWER (already computed by Analyzer — use this as your source):",
        session.direct_answer or "Not available.",
        "",
        "CLINICAL SCENARIO:",
        session.clinical_scenario or "Not available.",
        "",
        "USEFUL INFO / MNEMONIC:",
        session.useful_info or "Not available.",
        "",
        "STUDENT ATTEMPT LOG:",
    ]

    if attempt_lines:
        prompt_parts.extend(attempt_lines)
    else:
        prompt_parts.append("  No attempts recorded.")

    prompt_parts.extend([
        "",
        "STUDENT MISTAKES:",
    ])

    if mistake_lines:
        prompt_parts.extend(mistake_lines)
    else:
        prompt_parts.append("  No mistakes recorded — great work!")

    prompt_parts.extend([
        "",
        "Now write the full mastery summary.",
    ])

    prompt = "\n".join(prompt_parts)

    return llm_chat(REVEAL_SYSTEM_PROMPT, [{"role": "user", "content": prompt}])
