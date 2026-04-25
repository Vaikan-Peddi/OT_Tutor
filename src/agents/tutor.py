"""
agents/tutor.py — Socratic tutor agent; the only agent that speaks to the student.

Spec requirement: the bot is STRICTLY FORBIDDEN from giving a direct answer
in the first two turns (turns 2-3 in tutoring phase, since turn 1 is rapport).
It must use retrieved context to ask a leading question only.
"""

from src.llm import llm_chat

TUTOR_SYSTEM_PROMPT = """\
You are a warm, Socratic OT tutor following the "Tutor-not-Teller" philosophy.
Your job is to guide the student toward the answer through questions — never state it directly.

STRICT RULES (non-negotiable):
1. For the first 2 tutoring turns: you are FORBIDDEN from giving any direct definition \
or direct answer. You MUST ask exactly one leading question based on the textbook context.
2. After turn 2: you may affirm correct reasoning, gently correct mistakes, and push deeper — \
but still never give the full answer away.
3. Ask exactly ONE question per turn. Never stack multiple questions.
4. In ASSESSMENT phase: present the clinical scenario and ask the student to reason through it.
5. In REVEALED phase: you may give a complete summary with clinical pearls.
6. Keep responses to 3-4 sentences maximum (except in revealed phase).
7. If reveal_unlocked is True and reveal_offered is False: end your reply by mentioning \
the student can type /reveal to see the full answer.
"""


def run_tutor(student_message: str, analysis: dict, session) -> str:
    """
    Tutor Agent — generates the reply shown to the student.

    Args:
        student_message: raw student input this turn
        analysis:        parsed output from AnalyzerAgent
        session:         QuestionSession (phase, turn_count, history, etc.)

    Returns:
        Tutor's reply as a plain string.
    """
    proximity = analysis.get("proximity_score", 0)
    quality   = analysis.get("student_answer_quality", "unanswered")
    mistake   = analysis.get("mistake_excerpt")
    # None when masked (turns 1-3), actual answer after turn 3
    revealed_answer = analysis.get("direct_answer_for_tutor")

    lines = [
        f"[PHASE: {session.phase}]",
        f"[TURN: {session.turn_count}]",
        f"[SOCRATIC_LOCK: {'YES — do NOT give any direct answer or definition this turn' if session.turn_count <= 3 else 'NO — can affirm and deepen, but still guide Socratically'}]",
        f"[PROXIMITY: {proximity}/100]",
        f"[QUALITY: {quality}]",
        "",
    ]

    if revealed_answer:
        lines += [
            "DIRECT ANSWER (now unlocked — you may use this to deepen guidance, NOT to state verbatim):",
            revealed_answer,
            "",
        ]
    else:
        lines.append("DIRECT ANSWER: [MASKED — do not reveal or hint at the answer directly]")
        lines.append("")

    lines += ["SOCRATIC QUESTIONS (pick the most fitting one for this turn):"]
    for q in analysis.get("related_questions", []):
        lines.append(f"  - {q}")

    if session.phase == "assessment" and session.clinical_scenario:
        lines += ["", "CLINICAL SCENARIO TO PRESENT:", session.clinical_scenario]

    if mistake:
        lines += ["", f"MISTAKE TO GENTLY CORRECT: {mistake}"]

    lines += [
        "",
        f"REVEAL_UNLOCKED: {session.reveal_unlocked}",
        f"REVEAL_OFFERED:  {session.reveal_offered}",
    ]

    ctx_block = "\n".join(lines)

    # Full message list: history + this turn with hidden context appended
    messages = list(session.conversation) + [
        {
            "role": "user",
            "content": f"{student_message}\n\n[TUTOR CONTEXT — not visible to student]\n{ctx_block}",
        }
    ]

    reply = llm_chat(TUTOR_SYSTEM_PROMPT, messages)

    # Flip the flag so we don't mention /reveal again next turn
    if session.reveal_unlocked and not session.reveal_offered:
        session.reveal_offered = True

    return reply
