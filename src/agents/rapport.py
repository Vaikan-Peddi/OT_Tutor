"""
agents/rapport.py — Phase 0: Rapport Agent.

Spec requirement:
  "Open with context-aware chitchat (e.g., 'Ready for the lab exam?') to build engagement."

This is a PROACTIVE greeting sent by the tutor BEFORE the student asks anything.
It requires no student input — the Manager calls it automatically when a new
conversation starts. The student's first message after this will be their question,
which then flows into the initializer + tutoring loop.

If the student has weak topics from previous sessions, the greeting references them
to feel personal. Otherwise it's a warm general opener.
"""

from src.llm import llm_chat

_RAPPORT_SYSTEM = """\
You are a warm Occupational Therapy study companion opening a tutoring session \
at the University at Buffalo.
Write a short, friendly greeting to the student.

Rules:
- 2-3 sentences maximum.
- If weak topics are provided, briefly reference ONE of them to show continuity \
  (e.g. Last time we tackled radial nerve palsy — nice work pushing through that.).
- End with ONE open, encouraging question inviting the student to share what they \
  want to work on today.
- Do NOT answer anatomy or clinical questions. Do NOT start tutoring yet.
- Sound like a knowledgeable study partner, not a formal system.
- Output plain text only — do NOT wrap your response in quotation marks, \
  do NOT use markdown or bullet points.
"""


def run_rapport(weak_topics: list) -> str:
    """
    Generate the proactive opening greeting.
    Called by the Manager before any student message is received.

    Args:
        weak_topics: list of topic label strings from previous sessions (may be empty)

    Returns:
        A short warm greeting string to send to the student.
    """
    if weak_topics:
        recent = weak_topics[-2:]
        context = f"Topics this student has struggled with recently: {', '.join(recent)}."
    else:
        context = "No previous session data — this is likely their first session."

    prompt = "\n".join([
        context,
        "",
        "Write the opening greeting now.",
    ])

    result = llm_chat(_RAPPORT_SYSTEM, [{"role": "user", "content": prompt}])
    return result.strip().strip('"').strip("'")
