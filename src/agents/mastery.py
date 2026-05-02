"""
agents/mastery.py — MasteryAgent.

Triggered when the student types /mastery (unlocks after turn 3).
Generates a structured post-session summary with holistic session evaluation.
"""

from src.llm import llm_chat

_MASTERY_SYSTEM = """\
You are an expert OT educator writing a post-session mastery summary for a \
University at Buffalo student.

Write clearly under EXACTLY these 6 section headers (use them verbatim):

## Overall Performance
Give a holistic, session-wide evaluation in 3-4 sentences — NOT a turn-by-turn list.
Assess: how well the student understood the core concept by the end, whether their \
reasoning improved across the session, and how they engaged with the clinical scenario.
Be warm and specific. Reference the improvement trajectory and assessment scores provided.\
Do NOT assign a letter grade or numeric grade.

## Answer
State the complete, textbook-grounded answer to the student's question.
Ground every claim in the retrieved context provided. Be thorough.

## Your Journey
Summarise how the student's understanding developed across the session in 3-5 sentences.
Focus on the improvement arc — did understanding grow, plateau, or regress?
Acknowledge specific things they got right and correct mistakes warmly and precisely.
Do NOT list every turn individually.

## Clinical Application
Present the clinical scenario from the session and explain the model answer —
how the condition presents clinically and what OT interventions would follow.

## Clinical Pearl
Give one memorable mnemonic or high-yield fact the student can take away immediately.

## What to Study Next
If the student had gaps or made mistakes, suggest 1-2 specific topics to review next.

Tone: warm, academic mentor. Ground the Answer strictly in the provided context.\
"""


def run_mastery(session) -> str:
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

    mistake_lines = [
        f"  - [{m.get('topic', '?')}] {m.get('excerpt', '')}"
        for m in session.mistakes
    ]

    # Compute holistic session stats
    all_scores        = [a["proximity_score"] for a in session.attempts if a.get("proximity_score") is not None]
    assessment_scores = [a["proximity_score"] for a in session.attempts
                         if a.get("phase") == "assessment" and a.get("proximity_score") is not None]

    avg_all        = round(sum(all_scores) / len(all_scores))        if all_scores        else None
    avg_assessment = round(sum(assessment_scores) / len(assessment_scores)) if assessment_scores else None
    best_score     = max(all_scores) if all_scores else None

    # Improvement trajectory: compare first-half vs second-half average
    trajectory = "no data"
    if len(all_scores) >= 2:
        mid = len(all_scores) // 2
        first_avg = sum(all_scores[:mid]) / mid
        second_avg = sum(all_scores[mid:]) / len(all_scores[mid:])
        if second_avg > first_avg + 5:
            trajectory = "improving"
        elif second_avg < first_avg - 5:
            trajectory = "declining"
        else:
            trajectory = "consistent"

    stats_block = "\n".join([
        f"  Total attempts: {len(session.attempts)}",
        f"  Average score (all phases): {avg_all}/100" if avg_all is not None else "  Average score: N/A",
        f"  Average score (assessment only): {avg_assessment}/100" if avg_assessment is not None else "  Assessment score: N/A",
        f"  Best score: {best_score}/100" if best_score is not None else "  Best score: N/A",
        f"  Score trajectory: {trajectory}",
    ])

    prompt = "\n".join([
        "ORIGINAL QUESTION:",
        session.original_question,
        "",
        "SESSION STATISTICS (use for Overall Performance grade):",
        stats_block,
        "",
        "RETRIEVED TEXTBOOK CONTEXT (ground the Answer section here):",
        session.retrieved_context or "No context available.",
        "",
        "DIRECT ANSWER (use as primary source for the Answer section):",
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

    return llm_chat(_MASTERY_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=1200)
