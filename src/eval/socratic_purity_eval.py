"""
eval/socratic_purity_eval.py — Socratic Purity evaluation.

Measures whether the tutor's hint turns (turns 1 and 2) avoid leaking the
direct answer before the reveal turn (turn 3).

Conversation index layout (from eval_transcripts.json):
  [0] assistant — rapport
  [1] user      — student question
  [2] assistant — Hint 1   ← evaluated
  [3] user      — student T2
  [4] assistant — Hint 2   ← evaluated
  [5] user      — student T3
  [6] assistant — Reveal
  ...

Metrics per transcript:
  keyword_leaked   — any direct-answer key term appears verbatim in Hint 1 or Hint 2
  hints_ask_questions — both hints contain at least one "?"
  llm_purity_hint1 — LLM judge score 0-1 for Hint 1
  llm_purity_hint2 — LLM judge score 0-1 for Hint 2
  purity_score     — composite (0-1, higher = more Socratic)

Composite formula:
  purity_score = 0.5 * avg(llm_purity_hint1, llm_purity_hint2)
               + 0.3 * (1 if NOT keyword_leaked else 0)
               + 0.2 * (1 if hints_ask_questions else 0)
"""

import json
import re

import numpy as np

from src.llm import llm_chat
from src.config import EVAL_OUTPUT_DIR


_LLM_JUDGE_SYSTEM = """\
You are evaluating whether a tutor hint is Socratic or whether it leaks the answer.

A hint is FULLY SOCRATIC (score 1.0) when it:
  - Asks a leading question without naming or defining the correct answer.
  - Guides the student's thinking without confirming or denying any specific term.

A hint LEAKS THE ANSWER (score 0.0) when it:
  - Directly names the correct structure, nerve, muscle, or bone.
  - Defines or paraphrases the answer in a way that makes it obvious.
  - Confirms the student's correct guess by repeating the key term.

Output ONLY valid JSON — no markdown, no prose:
{"purity_score": <float 0.0 to 1.0>, "leaked": <true|false>, "reason": "<one sentence>"}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _key_terms(direct_answer: str) -> set:
    """Extract significant words (4+ chars) from the direct answer."""
    stop = {
        "this", "that", "with", "from", "have", "also", "been", "when",
        "more", "into", "they", "their", "there", "which", "both", "some",
        "each", "such", "will", "most", "than", "then", "what", "where",
        "does", "very", "just", "only", "about", "after", "before",
    }
    words = re.findall(r"[a-zA-Z]{4,}", direct_answer.lower())
    return {w for w in words if w not in stop}


def _keyword_leak(hint: str, terms: set) -> tuple:
    """Return (leaked: bool, found_terms: list)."""
    lower = hint.lower()
    found = [t for t in terms if t in lower]
    return bool(found), found


def _llm_judge(hint: str, direct_answer: str, question: str) -> dict:
    prompt = (
        f"QUESTION BEING TUTORED:\n{question}\n\n"
        f"CORRECT ANSWER (use only for comparison — do not reveal):\n{direct_answer}\n\n"
        f"TUTOR HINT TO EVALUATE:\n{hint}"
    )
    try:
        raw   = llm_chat(_LLM_JUDGE_SYSTEM, [{"role": "user", "content": prompt}])
        clean = re.sub(r"```[a-z]*", "", raw).strip().strip("`").strip()
        return json.loads(clean)
    except Exception:
        return {"purity_score": 0.5, "leaked": False, "reason": "parse error"}


def _get_assistant_turn(conversations: list, idx: int) -> str:
    if idx < len(conversations) and conversations[idx]["role"] == "assistant":
        return conversations[idx]["content"]
    return ""


# ── Per-transcript scorer ─────────────────────────────────────────────────────

def score_purity(transcript: dict) -> dict:
    convs         = transcript["conversations"]
    direct_answer = transcript["hidden_direct_answer"]
    question      = transcript["question"]

    hint1 = _get_assistant_turn(convs, 2)
    hint2 = _get_assistant_turn(convs, 4)

    if not hint1 and not hint2:
        return {
            "id": transcript["id"], "question": question,
            "error": "hint turns not found", "purity_score": None,
        }

    terms = _key_terms(direct_answer)

    leak1, found1 = _keyword_leak(hint1, terms)
    leak2, found2 = _keyword_leak(hint2, terms)
    keyword_leaked = leak1 or leak2

    judge1 = _llm_judge(hint1, direct_answer, question) if hint1 else {"purity_score": 1.0, "leaked": False, "reason": "no hint"}
    judge2 = _llm_judge(hint2, direct_answer, question) if hint2 else {"purity_score": 1.0, "leaked": False, "reason": "no hint"}

    has_q1 = "?" in hint1
    has_q2 = "?" in hint2
    hints_ask_questions = has_q1 and has_q2

    llm_avg = (judge1["purity_score"] + judge2["purity_score"]) / 2
    purity_score = (
        0.5 * llm_avg
        + 0.3 * (0 if keyword_leaked else 1)
        + 0.2 * (1 if hints_ask_questions else 0)
    )

    return {
        "id"      : transcript["id"],
        "question": question,
        "purity_score"      : round(purity_score, 3),
        "keyword_leaked"    : keyword_leaked,
        "hints_ask_questions": hints_ask_questions,
        "hint1": {
            "text"           : hint1[:300],
            "keyword_leaked" : leak1,
            "leaked_terms"   : found1,
            "has_question"   : has_q1,
            "llm_purity"     : round(judge1["purity_score"], 3),
            "llm_leaked"     : judge1.get("leaked", False),
            "llm_reason"     : judge1.get("reason", ""),
        },
        "hint2": {
            "text"           : hint2[:300],
            "keyword_leaked" : leak2,
            "leaked_terms"   : found2,
            "has_question"   : has_q2,
            "llm_purity"     : round(judge2["purity_score"], 3),
            "llm_leaked"     : judge2.get("leaked", False),
            "llm_reason"     : judge2.get("reason", ""),
        },
    }


# ── Main eval runner ──────────────────────────────────────────────────────────

def run_socratic_purity_eval(transcripts: list) -> dict:
    """
    Args:
        transcripts: list of dicts from eval_transcripts.json
    Returns aggregate + per-transcript results.
    """
    EVAL_OUTPUT_DIR.mkdir(exist_ok=True)
    results = []

    for t in transcripts:
        print(f"Scoring purity {t['id']}…")
        results.append(score_purity(t))

    valid = [r for r in results if r.get("purity_score") is not None]

    mean_purity      = float(np.mean([r["purity_score"]      for r in valid]))
    keyword_leak_rate = float(np.mean([1 if r["keyword_leaked"] else 0 for r in valid]))
    question_rate     = float(np.mean([1 if r["hints_ask_questions"] else 0 for r in valid]))

    print(f"\nMean Socratic Purity Score : {mean_purity:.3f}  (0=leaked, 1=fully Socratic)")
    print(f"Keyword Leak Rate          : {keyword_leak_rate:.3f}  (fraction of sessions with answer term in hints)")
    print(f"Both Hints Ask Questions   : {question_rate:.3f}  (fraction where both hints end with '?')")

    out_path = EVAL_OUTPUT_DIR / "socratic_purity_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"✓ Saved to {out_path}")

    return {
        "aggregate": {
            "mean_purity_score"  : mean_purity,
            "keyword_leak_rate"  : keyword_leak_rate,
            "question_rate"      : question_rate,
        },
        "per_transcript": results,
    }
