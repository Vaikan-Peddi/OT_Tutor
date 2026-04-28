"""
agents/analyzer.py — two-stage analysis pipeline.

Stage 1  run_initializer()   called ONCE per session on the first tutoring turn.
         Input:  RAG context + original question (no student answer yet).
         Output: direct_answer, clinical_scenario, related_questions,
                 useful_info, topic_label  — all stored immutably in the session.

Stage 2  run_analyzer()      called every subsequent tutoring/assessment turn.
         Input:  student message + conversation history (no RAG context needed).
         Output: student_answer_quality, proximity_score,
                 attempt_summary, mistake_excerpt  — lightweight, focused.

Why the split?
- direct_answer is generated once from clean context → stays consistent → easy to mask.
- The per-turn analyzer has a tiny JSON schema (4 fields) → far fewer parse errors.
- The Manager controls exactly when direct_answer is passed to the Tutor (after turn 3).
"""

import json
import re
from src.llm import llm_chat


# ─────────────────────────────────────────────────────────────────────────────
# Shared: robust JSON extractor (used by both stages)
# ─────────────────────────────────────────────────────────────────────────────

def _close_json(text: str) -> str:
    """Append missing closing brackets/braces to truncated JSON output."""
    stack = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack and stack[-1] == ch:
            stack.pop()
    return text + "".join(reversed(stack))


def _quote_unquoted_values(text: str) -> str:
    """
    Quote bare string values that the LLM forgot to wrap in quotes.
    e.g.  "direct_answer": Insufficient context,
      →   "direct_answer": "Insufficient context",
    Numbers, booleans, null, arrays, and objects are left untouched.
    """
    def repl(m):
        return f'{m.group(1)}: "{m.group(2).strip()}"'

    return re.sub(
        r'("[\w_]+")\s*:\s*'           # "key":
        r'(?!["\[{\d\-]'               # not already a string/array/object/number
        r'|true\b|false\b|null\b)'     # not a boolean or null
        r'([^\n\[{},]+)',              # bare value up to delimiter
        repl,
        text,
    )


def _extract_json(raw: str, fallback: dict) -> dict:
    """
    Multi-pass extraction handling every common LLM failure mode:
      1. Direct parse (ideal)
      2. Markdown-fenced  ```json ... ```
      3. JSON buried in prose — find outermost { }
      4. Trailing-comma / JS-comment cleanup
      5. Quote unquoted string values  (e.g. "key": Some text)
      6. Close truncated JSON          (missing ] or } at end)
      7. Unrecoverable → return fallback
    """
    text = raw.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Use the largest {...} block found, even if the JSON was cut off
    brace = re.search(r"\{[\s\S]*", text)
    if brace:
        candidate = brace.group(0)

        # Pass 4: trailing commas + JS comments
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        candidate = re.sub(r"//[^\n]*", "", candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Pass 5: quote unquoted string values
        candidate = _quote_unquoted_values(candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        # Pass 6: close truncated JSON then retry both fixes
        candidate = _close_json(candidate)
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        candidate = _quote_unquoted_values(candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    print(f"[Analyzer] JSON extraction failed. Raw:\n{raw[:400]}\n")
    return fallback.copy()


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Initializer  (called once, from RAG context)
# ─────────────────────────────────────────────────────────────────────────────

_INIT_SYSTEM = """\
You are a knowledge-extraction agent for a Socratic OT tutoring system.
Given a student's question and retrieved textbook passages, extract structured knowledge.
You NEVER speak to the student. Output ONLY a single JSON object — no markdown, no prose.

JSON schema:
{
  "direct_answer": "<2-4 sentences. Complete answer grounded strictly in the context passages.>",
  "clinical_scenario": "<1-2 sentences. A clinical case a student could reason through.>",
  "related_questions": [
    "<1 sentence. Easy Socratic question to open the topic.>",
    "<1 sentence. Medium question on a connected concept.>",
    "<1 sentence. Hard clinical application question.>"
  ],
  "useful_info": "<1 sentence. One high-yield mnemonic or clinical pearl from the context.>",
  "topic_label": "<2-5 words lowercase. Label for this topic.>"
}

Rules:
- Keep EVERY field short — the entire JSON must fit in one response.
- direct_answer: if context is insufficient, write exactly: Insufficient context.
- related_questions: exactly 3 strings, ordered easy to hard.
- topic_label: lowercase, concise (e.g. "ulnar nerve function").
- Do NOT use newlines inside any string value.
"""

_INIT_FALLBACK = {
    "direct_answer"    : "Insufficient context.",
    "clinical_scenario": "A patient presents with a peripheral nerve injury. Describe the deficit.",
    "related_questions": [
        "What do you already know about this structure?",
        "Where in the body does this structure originate?",
        "What happens clinically when this structure is damaged?",
    ],
    "useful_info"  : "",
    "topic_label"  : "anatomy topic",
}


def run_initializer(original_question: str, context: str) -> dict:
    """
    Stage 1 — extract stable knowledge from RAG context.
    Called exactly once per session, before any student answer exists.

    Returns dict with keys: direct_answer, clinical_scenario,
    related_questions, useful_info, topic_label.
    """
    prompt = "\n".join([
        "STUDENT QUESTION:",
        original_question,
        "",
        "RETRIEVED TEXTBOOK CONTEXT:",
        context or "No context retrieved.",
        "",
        "Output the JSON object now.",
    ])

    raw    = llm_chat(_INIT_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=2048)
    result = _extract_json(raw, _INIT_FALLBACK)

    # Fill any missing keys
    for key, default in _INIT_FALLBACK.items():
        if key not in result:
            result[key] = default

    rq = result.get("related_questions", [])
    if not isinstance(rq, list) or len(rq) < 3:
        result["related_questions"] = _INIT_FALLBACK["related_questions"]

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Per-turn Analyzer  (called every tutoring/assessment turn)
# ─────────────────────────────────────────────────────────────────────────────

_ANALYZER_SYSTEM = """\
You are a student-response evaluator for a Socratic OT tutoring system.
Given the original question, the gold-standard answer, the conversation history, \
and the student's latest message, evaluate the student's response.
Output ONLY a single JSON object — no markdown, no prose.

JSON schema:
{
  "student_answer_quality": "<one of: correct, partial, wrong, unanswered>",
  "proximity_score": <integer 0 to 100>,
  "attempt_summary": "<1-2 sentences on what the student got right or wrong, or null>",
  "mistake_excerpt": "<verbatim wrong claim from student under 80 chars, or null>"
}

Rules:
- student_answer_quality is "unanswered" if the student only asked a question without attempting an answer.
- proximity_score: 0=no attempt or completely wrong, 50=partially correct, 100=fully correct.
- attempt_summary and mistake_excerpt are null when quality is "unanswered".
- mistake_excerpt must be a verbatim quote from the student's message, not a paraphrase.
"""

_ANALYZER_FALLBACK = {
    "student_answer_quality": "unanswered",
    "proximity_score"       : 0,
    "attempt_summary"       : None,
    "mistake_excerpt"       : None,
}


def run_analyzer(
    student_message: str,
    original_question: str,
    direct_answer: str,
    conversation_history: list,
) -> dict:
    """
    Stage 2 — evaluate the student's response each turn.
    Does NOT receive RAG context (that's already in direct_answer).
    Does NOT regenerate direct_answer, scenario, or questions.

    Args:
        student_message      : the student's input this turn
        original_question    : the question that opened this session
        direct_answer        : the gold-standard answer from the initializer
        conversation_history : full session conversation so far (LLM format)

    Returns dict with keys: student_answer_quality, proximity_score,
    attempt_summary, mistake_excerpt.
    """
    history_snippet = "No prior turns yet."
    if conversation_history:
        recent = conversation_history[-6:]
        history_snippet = "\n".join(
            f"{t['role'].upper()}: {t['content'][:250]}" for t in recent
        )

    prompt = "\n".join([
        "ORIGINAL QUESTION:",
        original_question,
        "",
        "GOLD-STANDARD ANSWER (do not reveal to student — use only for evaluation):",
        direct_answer,
        "",
        "CONVERSATION HISTORY (last 6 turns):",
        history_snippet,
        "",
        "STUDENT MESSAGE THIS TURN:",
        student_message,
        "",
        "Output the JSON evaluation now.",
    ])

    raw    = llm_chat(_ANALYZER_SYSTEM, [{"role": "user", "content": prompt}])
    result = _extract_json(raw, _ANALYZER_FALLBACK)

    for key, default in _ANALYZER_FALLBACK.items():
        if key not in result:
            result[key] = default

    return result
