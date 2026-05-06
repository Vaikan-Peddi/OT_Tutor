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
You are a warm Socratic OT tutor. Your ONLY job is to ask ONE leading hint question.

ABSOLUTE RULES — ZERO EXCEPTIONS:
1. NEVER use, spell, echo, or paraphrase the FORBIDDEN TERMS — they ARE the answer.
   Even if the student writes them, do NOT confirm, repeat, or imply them.
2. Do NOT define anatomy/neuroscience terms directly.
3. Your response must end with EXACTLY ONE question (last sentence ends with ?).
4. Total response: 1-2 sentences maximum. The question itself, with at most one brief setup clause.
5. If the student is on the right track, acknowledge their direction in one clause, then push deeper.
6. Do NOT open with "Great question!", "Interesting!", or any filler phrase.
7. Do NOT state or hint at the answer — only ask a question that steers thinking toward it.
8. Ask about mechanism, function, or clinical consequence — never about terminology directly.
9. TOPIC LOCK — critical: your question MUST stay strictly on the topic stated in STUDENT QUESTION.
   Do NOT drift to related but different anatomy. Example: if the question is about finger flexion,
   every hint must be about finger flexion muscles — NOT wrist flexors, NOT elbow flexors.\
"""

_REVEAL_SYSTEM = """\
You are a warm OT tutor. The student has had 2 hint turns. It is now time to reveal the full answer.

Write a single flowing response (no headings, no numbered lists) that:
1. Opens by stating the direct answer clearly and accurately, grounded in the DIRECT ANSWER provided.
2. Transitions naturally into the clinical scenario (e.g. "Now let's put this into practice…").
3. Closes with ONE question asking the student to reason through the patient presentation and \
   suggest appropriate OT strategies.

Keep the whole response under 180 words. Be warm and precise — state the answer confidently.\
"""

_ASSESSMENT_SYSTEM = """\
You are a warm OT tutor evaluating a student's clinical reasoning.

Write a flowing response (no headings, no numbers) with exactly three parts:

FEEDBACK (2-3 sentences): Compare the student's response directly to the gold-standard answer.
  - Score ≥75 (correct): Affirm clearly and name exactly what they got right.
  - Score 25-74 (partial): Acknowledge what's right first, then explain the specific gap.
  - Score <25 (wrong): Be warm but direct — correct the misconception with the right information.

CLINICAL PEARL (1 sentence): One memorable mnemonic or high-yield fact tied to this specific topic.

NEXT STEP (1 sentence):
  - If mastery is unlocked (MASTERY_UNLOCKED=True): "Press the Mastery button below for your full session summary."
  - If mastery not yet unlocked: encourage them to keep working toward it.
  - If this is a follow-up assessment turn: ask them to address the weakest part of their answer.

Keep the whole response under 150 words. Be specific — reference exact clinical terms from the answer.\
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
                f"TOPIC LOCK — every hint must be strictly about: {session.original_question}",
                "",
                "IMPORTANT: This is the student's FIRST message. Treat it as an opening question "
                "or initial thought — do NOT evaluate whether it is correct or incorrect. "
                "Ignore quality/proximity scores this turn and jump straight to ONE leading hint question.",
                "",
                "OPENING HINT QUESTIONS — pick the most fitting one and rephrase if needed:",
                hint_questions,
                "",
                "STUDENT'S FIRST MESSAGE:",
                student_message,
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
                f"TOPIC LOCK — every hint must be strictly about: {session.original_question}",
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
        return "Press the Mastery button above to see your full session summary."

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
