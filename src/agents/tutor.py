"""
agents/tutor.py — Socratic tutor agent; the only agent that speaks to the student.
"""

from src.llm import llm_chat

TUTOR_SYSTEM_PROMPT = """\
You are a warm, Socratic OT tutor. Your job is to guide the student toward the answer — never give it away directly.

Rules:
- Ask ONE guiding question per turn. Never ask multiple questions.
- If the student is wrong, gently correct the specific mistake, then redirect.
- If the student is close (proximity ≥ 70), affirm and push for more detail.
- In ASSESSMENT phase: present the clinical scenario and ask how they would manage it.
- In REVEALED phase: you may summarize the full answer and add clinical pearls.
- Keep responses ≤ 4 sentences unless in revealed phase.
- If reveal_offered is False and reveal_unlocked is True, mention once that they can type /reveal to see the full answer.
"""


def run_tutor(student_message: str, analysis: dict, session) -> str:
    """
    Tutor agent — generates the reply the student sees.

    Args:
        student_message: raw student input
        analysis:        output from AnalyzerAgent
        session:         QuestionSession (read-only here)
    """
    # Build a compact context block for the tutor
    ctx_block = (
        f"[PHASE: {session.phase}] "
        f"[TURN: {session.turn_count}] "
        f"[PROXIMITY: {analysis.get('proximity_score', 0)}] "
        f"[QUALITY: {analysis.get('student_answer_quality', 'unanswered')}]\n"
        f"RELATED QUESTIONS (pick the most appropriate):\n"
        + "\n".join(f"  - {q}" for q in analysis.get("related_questions", []))
        + (f"\n\nCLINICAL SCENARIO (use only in assessment phase):\n{session.clinical_scenario}"
           if session.phase == "assessment" else "")
        + (f"\n\nREVEAL UNLOCKED: {session.reveal_unlocked}, OFFERED: {session.reveal_offered}" )
        + (f"\n\nMISTAKE TO CORRECT: {analysis.get('mistake_excerpt')}"
           if analysis.get("mistake_excerpt") else "")
    )

    messages = list(session.conversation) + [
        {"role": "user", "content": f"{student_message}\n\n[TUTOR CONTEXT]\n{ctx_block}"}
    ]

    reply = llm_chat(TUTOR_SYSTEM_PROMPT, messages)

    # Mark reveal as offered so we don't repeat it
    if session.reveal_unlocked and not session.reveal_offered:
        session.reveal_offered = True

    return reply
