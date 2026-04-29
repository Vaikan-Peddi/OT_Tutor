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

ABSOLUTE RULES — ZERO EXCEPTIONS:
1. NEVER use, spell, echo, or paraphrase the FORBIDDEN TERMS listed in the context block.
   Those terms ARE the answer. Even if the student says them, do NOT repeat or confirm them.
2. Do NOT define any key anatomy/neuroscience terms directly.
3. Ask EXACTLY ONE short question that steers the student's thinking without naming the answer.
4. Your entire response must be 2-3 sentences maximum.
5. If the student seems close, acknowledge their reasoning direction (not the specific term) and push deeper.
6. Do NOT say "Great question!" or similar filler openers.

Think of the FORBIDDEN TERMS as words that must never appear in your output under any circumstances.\
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

    # ── Image-session prefix (injected into every context block) ─────────
    image_prefix = ""
    if getattr(session, "image_mode", False):
        identified_as = getattr(session, "image_identified_as", "") or "anatomical diagram"
        image_prefix = (
            f"[IMAGE SESSION] The student uploaded a diagram. "
            f"Gemini Vision identified it as: {identified_as}. "
            f"Frame your response around this specific diagram.\n\n"
        )

    # ── Build the user-side context block (hidden from student) ──────────
    if phase == "tutoring":
        system = _HINT_SYSTEM
        direct_answer = analysis.get("direct_answer", "")

        # Build the forbidden-term list from the direct answer.
        # These are the exact words the tutor must NEVER say during hints.
        forbidden_terms = ", ".join(sorted({
            w.lower() for w in direct_answer.replace(',', '').replace('.', '').split()
            if len(w) > 3
        }))
        forbidden_line = f"FORBIDDEN TERMS — never use any of these words in your response: {forbidden_terms}"

        def mask_keywords(q):
            for word in set(direct_answer.replace(',', '').replace('.', '').split()):
                if len(word) > 3:
                    q = q.replace(word, "____")
            return q

        masked_question = session.original_question
        for word in set(direct_answer.replace(',', '').replace('.', '').split()):
            if len(word) > 3:
                masked_question = masked_question.replace(word, "____")

        if session.turn_count == 1:
            # Turn 1: no prior exchange — use static hint questions as scaffolding
            hint_questions = "\n".join(
                f"  - {mask_keywords(q)}" for q in analysis.get("related_questions", [])
            )
            ctx_block = "\n".join([
                forbidden_line,
                "",
                "TURN: 1 of 2 (first hint)",
                f"STUDENT QUESTION: {masked_question}",
                "",
                "OPENING HINT QUESTIONS — pick the most fitting one and rephrase if needed:",
                hint_questions,
                "",
                "STUDENT'S ATTEMPT THIS TURN:",
                student_message,
                "",
                f"QUALITY: {analysis.get('student_answer_quality', 'unanswered')}",
                f"PROXIMITY: {analysis.get('proximity_score', 0)}/100",
                analysis.get("attempt_summary") or "",
            ])
        else:
            # Turn 2: build on the student's turn-1 response and the first hint
            prev_hint = ""
            for msg in reversed(session.conversation):
                if msg["role"] == "assistant":
                    prev_hint = msg["content"]
                    break

            ctx_block = "\n".join([
                forbidden_line,
                "",
                "TURN: 2 of 2 (final hint — answer revealed next turn)",
                f"STUDENT QUESTION: {masked_question}",
                "",
                "YOUR PREVIOUS HINT (do NOT repeat this angle):",
                prev_hint or "No previous hint.",
                "",
                "STUDENT'S RESPONSE TO YOUR HINT:",
                student_message,
                "",
                f"QUALITY: {analysis.get('student_answer_quality', 'unanswered')}",
                f"PROXIMITY: {analysis.get('proximity_score', 0)}/100",
                analysis.get("attempt_summary") or "",
                "",
                "INSTRUCTION: Ask ONE follow-up question that directly reacts to the student's "
                "response above. If they were partially right, push deeper on what they got right. "
                "If they were wrong or off-track, redirect from a different angle. "
                "Do NOT repeat the same angle as your previous hint. "
                "Do NOT confirm whether the student's answer is correct — that happens on turn 3.",
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
                f"[TUTOR CONTEXT — internal only, not visible to student]\n"
                f"{image_prefix}{ctx_block}"
            ),
        }
    ]

    return llm_chat(system, messages)
