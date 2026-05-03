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
  "direct_answer": "<2-4 sentences answering the student question.>",
  "clinical_scenario": "<1-2 sentences. A clinical case a student could reason through.>",
  "related_questions": [
    "<1 sentence. Easy Socratic question strictly about the SAME topic as the student's question.>",
    "<1 sentence. Medium Socratic question that goes deeper on the SAME topic — not adjacent anatomy.>",
    "<1 sentence. Hard clinical application question still focused on the SAME topic.>"
  ],
  "useful_info": "<1 sentence. One high-yield mnemonic or clinical pearl.>",
  "topic_label": "<2-5 words lowercase. Label for this topic, derived from the student question.>"
}

Rules:
- Keep EVERY field short — the entire JSON must fit in one response.
- direct_answer: use the context passages if they are relevant. If the passages are not relevant
  or absent, answer from general anatomy/OT knowledge — be accurate and concise. Do NOT write
  "Insufficient context" — always provide a real answer.
- related_questions: exactly 3 strings, ordered easy to hard. ALL THREE must be about the exact
  same topic as the student's question — do NOT drift to related but different anatomy or concepts.
- topic_label: MUST be derived directly from the student question (e.g. "finger flexion muscles",
  "median nerve injury"). Never use generic placeholders like "anatomy topic".
- Do NOT use newlines inside any string value.
"""

_INIT_FALLBACK = {
    "direct_answer"    : "",   # populated by post-processing if empty
    "clinical_scenario": "A patient presents with a peripheral nerve injury. Describe the deficit.",
    "related_questions": [
        "What do you already know about this structure?",
        "Where in the body does this structure originate?",
        "What happens clinically when this structure is damaged?",
    ],
    "useful_info"  : "",
    "topic_label"  : "anatomy topic",
}


_TOPIC_STOPWORDS = {
    'what', 'which', 'where', 'when', 'who', 'how', 'does', 'is', 'are', 'was',
    'the', 'a', 'an', 'of', 'for', 'in', 'on', 'to', 'and', 'or', 'that', 'this',
    'these', 'those', 'with', 'from', 'by', 'about', 'can', 'will', 'would', 'could',
    'should', 'do', 'be', 'its', 'their', 'your', 'responsible', 'used', 'called',
    'named', 'give', 'tell', 'explain', 'describe', 'define', 'list', 'name',
}


def _topic_from_question(question: str) -> str:
    """Derive a 2-4 word topic label directly from the question text."""
    import re
    words = [w for w in re.findall(r'\b[a-z]+\b', question.lower())
             if len(w) > 3 and w not in _TOPIC_STOPWORDS]
    return " ".join(words[:4]) if words else "anatomy topic"


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

    # Safety net: if topic_label is generic or empty, derive from the question
    label = result.get("topic_label", "").strip().lower()
    if not label or label in ("anatomy topic", "anatomy", "topic"):
        result["topic_label"] = _topic_from_question(original_question)

    # Safety net: if direct_answer is empty or still says insufficient context,
    # ask the LLM for a brief general-knowledge answer
    answer = result.get("direct_answer", "").strip()
    if not answer or "insufficient context" in answer.lower():
        fallback_prompt = (
            f"Question: {original_question}\n\n"
            "Answer this anatomy/OT question using general knowledge. "
            "Be accurate and concise (2-3 sentences). "
            "If you are not certain, say so briefly rather than guessing details."
        )
        result["direct_answer"] = llm_chat(
            "You are a knowledgeable OT anatomy tutor. Answer the question accurately "
            "and concisely from general anatomy knowledge. Do not fabricate specific "
            "numbers or citations. If genuinely uncertain, hedge briefly.",
            [{"role": "user", "content": fallback_prompt}],
            max_tokens=300,
        )

    rq = result.get("related_questions", [])
    if not isinstance(rq, list) or len(rq) < 3:
        result["related_questions"] = _INIT_FALLBACK["related_questions"]

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Per-turn Analyzer  (called every tutoring/assessment turn)
# ─────────────────────────────────────────────────────────────────────────────

_ANALYZER_SYSTEM = """\
You are a student-response evaluator for a Socratic OT tutoring system.
This is a STUDY APP, not an exam. Be generous. Reward engagement and partial knowledge.
Output ONLY a single JSON object — no markdown, no prose.

JSON schema:
{
  "student_answer_quality": "<one of: correct, partial, wrong, unanswered>",
  "proximity_score": <integer 0 to 100>,
  "attempt_summary": "<1-2 sentences on what the student got right or wrong, or null>",
  "mistake_excerpt": "<short description of the gap or misconception, under 100 chars, or null>"
}

CONVERSATION HISTORY RULE (most important):
  Scan the ENTIRE conversation history before scoring.
  If the student correctly named, described, or identified the core answer (or its key
  components) at ANY point — even during hint turns — award at least 85.
  Students are guided to the answer through hints; credit them when they get there.

Scoring rubric for proximity_score:
  0-10:  No attempt, completely off-topic, or only asking questions (no answer attempt).
  11-35: Engages with the topic but core facts are wrong or missing.
  36-60: Right area — identified a related concept or partial mechanism, missing key detail.
  61-79: Mostly correct — right concept and reasoning, only minor gaps or loose wording.
  80-89: Very good — nearly complete, trivial omissions only.
  90-100: Correct answer stated directly (current turn OR anywhere in history). Award 95-100
          if the student explicitly names or describes the answer with reasonable precision.

Default bias: always round up between bands. A student who names the right structure
but misses one detail is in the 75-85 range. Never penalise for imprecise wording alone.

Rules for mistake_excerpt — set this field aggressively:
- score < 65 (wrong or partial): ALWAYS set mistake_excerpt. Write a short phrase describing
  exactly what the student got wrong or what was missing. Examples:
    "confused wrist flexors with finger flexors"
    "identified wrong nerve — said radial instead of median"
    "no knowledge of the topic — could not attempt"
    "partially correct but missed FDP as primary flexor"
- score ≥ 65: set to null only if the answer was genuinely correct.
- "I don't know", blank, or off-topic responses: set mistake_excerpt to
  "no knowledge demonstrated — could not answer [topic]".
- Do NOT leave mistake_excerpt null just because there is no verbatim wrong quote.
  A description of the gap is equally valid.

Other rules:
- student_answer_quality must be consistent with proximity_score:
    "correct"    if score ≥ 65
    "partial"    if 30 ≤ score < 65
    "wrong"      if 0 < score < 30
    "unanswered" if the student only asked a question without attempting an answer (score = 0)
- attempt_summary is null only when quality is "unanswered" with no engagement.
- Do NOT penalise the student for not using exact clinical terminology if the meaning is correct.
"""

_ANALYZER_FALLBACK = {
    "student_answer_quality": "unanswered",
    "proximity_score"       : 0,
    "attempt_summary"       : None,
    "mistake_excerpt"       : None,
}


def _looks_like_question(text: str) -> bool:
    content = text.strip().lower()
    if not content:
        return False
    if content.endswith('?'):
        return True
    return bool(
        re.match(
            r'^(who|what|when|where|why|how|is|are|can|could|should|would|did|do|does|will|may|might|must)\b',
            content,
        )
    )


def _normalize_quality(result: dict, student_message: str) -> dict:
    quality = result.get('student_answer_quality', 'unanswered')
    score = result.get('proximity_score', 0) or 0
    if quality == 'unanswered' and student_message.strip():
        if not _looks_like_question(student_message):
            if score >= 65:
                quality = 'correct'
            elif score >= 30:
                quality = 'partial'
            else:
                quality = 'wrong'
        elif result.get('mistake_excerpt'):
            # If the student made a wrong claim while still asking a question,
            # count it as a wrong attempt rather than a pure unanswered query.
            quality = 'wrong'

    result['student_answer_quality'] = quality

    if quality == 'unanswered':
        result['attempt_summary'] = None
        result['mistake_excerpt'] = None

    return result


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

    result = _normalize_quality(result, student_message)
    return result
