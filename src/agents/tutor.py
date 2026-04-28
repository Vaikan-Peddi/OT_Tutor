"""
agents/tutor.py — Socratic tutor agent; the ONLY agent that speaks to the student.

STRICT PIPELINE:
  Phase "tutoring" (turns 1-2): Ask ONE leading hint question. NEVER give or imply the answer.
  Phase "reveal"   (turn 3):    State the full direct answer clearly, then present the
                                 clinical scenario and ask the student to reason through it.
  Phase "assessment" (turn 4+): Evaluate the student's clinical reasoning and give feedback.
  Phase "mastery"  (/mastery):  Not handled here — goes to mastery agent.
"""

from src.llm import llm_chat

# ─────────────────────────────────────────────────────────────────────────────
# Phase-specific system prompts  (explicit, no ambiguity for the LLM)
# ─────────────────────────────────────────────────────────────────────────────

_HINT_SYSTEM = """\
You are a warm Socratic OT tutor. Your ONLY job right now is to ask ONE leading hint question.

STRICT RULES — NO EXCEPTIONS:
1. Do NOT state, imply, or hint at the direct answer to the student's question.
2. Do NOT define any key anatomy/neuroscience terms directly.
3. Ask EXACTLY ONE short question that activates the student's existing knowledge.
4. Your entire response must be 2-3 sentences maximum.
5. If the student already gave a partial answer, acknowledge it briefly, then push deeper with your question.
6. Do NOT say "Great question!" or similar filler openers.

Your question should lead the student toward the answer without giving it away.\
"""

_REVEAL_SYSTEM = """\
You are a warm OT tutor. The student has had 2 attempts. It is now time to REVEAL the answer.

Your response must include all of the following, but in a natural, conversational way (do NOT use section headings or numbers):
- Clearly state the direct answer, using the DIRECT ANSWER provided in the context. Be accurate and grounded.
- Present the clinical scenario from the context, smoothly transitioning from the answer to the scenario (e.g., "Now let's apply this..." or similar).
- End with a question inviting the student to explain what is happening to the patient and what OT strategies might help (e.g., "How would you explain what is happening to this patient, and what OT strategies might help?").

Keep the whole response under 200 words. Do not use explicit section headings or numbers.\
"""

_ASSESSMENT_SYSTEM = """\
You are a warm OT tutor evaluating a student's clinical reasoning.

YOUR RESPONSE MUST FOLLOW THIS EXACT STRUCTURE:

1. FEEDBACK (2-3 sentences): Evaluate the student's answer against the gold-standard.
   - If correct: affirm clearly, name exactly what they got right.
   - If partial: name what's right, then explain exactly what's missing.
   - If wrong: be warm but clear — correct the misconception directly.

2. CLINICAL PEARL (1 sentence): Give one memorable takeaway fact or mnemonic.

3. NEXT STEP (1 sentence): Tell the student what to do next.
   - If they haven't typed /mastery yet, say: "When you're ready for the full mastery summary, type /mastery"
   - If this is a follow-up assessment turn, ask them to try again or elaborate.

Keep the whole response under 150 words. Be warm and specific. Do not use explicit section headings or numbers.\
"""


def run_tutor(student_message: str, analysis: dict, session) -> str:
    """
    Tutor Agent — generates the reply shown to the student.

    Args:
        student_message: raw student input this turn
        analysis:        output from AnalyzerAgent + extra fields from Manager
        session:         QuestionSession (phase, turn_count, history, etc.)

    Returns:
        Tutor's reply as a plain string.
    """
    phase = session.phase

    # ── Build the user-side context block (hidden from student) ──────────
    if phase == "tutoring":
        system = _HINT_SYSTEM
        hint_questions = "\n".join(
            f"  - {q}" for q in analysis.get("related_questions", [])
        )
        ctx_block = "\n".join([
            f"TURN: {session.turn_count} of 2 (hint turns)",
            f"STUDENT QUESTION BEING TUTORED: {session.original_question}",
            "",
            "HINT QUESTIONS — pick the most fitting one and rephrase if needed:",
            hint_questions,
            "",
            "STUDENT'S ATTEMPT THIS TURN:",
            student_message,
            "",
            f"QUALITY: {analysis.get('student_answer_quality', 'unanswered')}",
            f"PROXIMITY: {analysis.get('proximity_score', 0)}/100",
            analysis.get("attempt_summary") or "",
        ])

    elif phase == "reveal":
        system = _REVEAL_SYSTEM
        ctx_block = "\n".join([
            "DIRECT ANSWER (state this clearly — the student has exhausted their 2 attempts):",
            analysis.get("direct_answer", "No answer available."),
            "",
            "CLINICAL SCENARIO (present this after giving the answer):",
            analysis.get("clinical_scenario", "No scenario available."),
        ])

    elif phase == "assessment":
        system = _ASSESSMENT_SYSTEM
        ctx_block = "\n".join([
            "GOLD-STANDARD ANSWER (use for evaluation — do NOT read verbatim):",
            analysis.get("direct_answer", ""),
            "",
            "CLINICAL SCENARIO THAT WAS PRESENTED:",
            analysis.get("clinical_scenario", ""),
            "",
            "STUDENT'S RESPONSE THIS TURN:",
            student_message,
            "",
            f"QUALITY: {analysis.get('student_answer_quality', 'unanswered')}",
            f"PROXIMITY: {analysis.get('proximity_score', 0)}/100",
            analysis.get("attempt_summary") or "",
            analysis.get("mistake_excerpt") and f"MISTAKE: {analysis['mistake_excerpt']}" or "",
            "",
            f"MASTERY_UNLOCKED: {analysis.get('mastery_unlocked', False)}",
        ])

    else:
        # Fallback (should not happen — mastery handled elsewhere)
        return "Type /mastery to see your full session summary."

    # ── Build message list: history + this turn with hidden context ───────
    messages = list(session.conversation) + [
        {
            "role": "user",
            "content": (
                f"{student_message}\n\n"
                f"[TUTOR CONTEXT — internal only, not visible to student]\n{ctx_block}"
            ),
        }
    ]

    return llm_chat(system, messages)
