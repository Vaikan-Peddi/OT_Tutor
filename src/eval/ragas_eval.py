"""
eval/ragas_eval.py — RAGAS-style faithfulness + answer relevance evaluation.
"""

import json
import re

import numpy as np
from sentence_transformers import SentenceTransformer

from src.llm import llm_chat
from src.config import EVAL_OUTPUT_DIR, EMBEDDING_MODEL

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


CLAIM_EXTRACTOR_PROMPT = """\
Extract every atomic factual claim from the answer below.
Output ONLY a JSON array of strings — no preamble, no markdown.
Example: ["The ulnar nerve innervates FCU.", "C8 and T1 contribute to the ulnar nerve."]
"""

CLAIM_VERIFIER_PROMPT = """\
Given a context and a single factual claim, decide whether the context supports the claim.
Output ONLY valid JSON:
{"supported": true | false, "reason": "one sentence"}
"""


def extract_claims(answer: str) -> list[str]:
    raw = llm_chat(CLAIM_EXTRACTOR_PROMPT, [{"role": "user", "content": f"ANSWER:\n{answer}"}])
    clean = re.sub(r"```[a-z]*", "", raw).strip().strip("`").strip()
    try:
        return json.loads(clean)
    except Exception:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if len(s.strip()) > 10]
        return sentences


def verify_claim(claim: str, context: str) -> dict:
    msg = f"CONTEXT:\n{context}\n\nCLAIM: {claim}"
    try:
        raw   = llm_chat(CLAIM_VERIFIER_PROMPT, [{"role": "user", "content": msg}])
        clean = re.sub(r"```[a-z]*", "", raw).strip().strip("`").strip()
        return json.loads(clean)
    except Exception:
        return {"supported": False, "reason": "parse error"}


def answer_relevance(answer: str, question: str) -> float:
    embedder = _get_embedder()
    orig_vec = embedder.encode([question])[0]
    try:
        gen_questions_raw = llm_chat(
            "Generate 3 questions that the following answer is trying to answer. "
            "Output ONLY a JSON array of 3 strings.",
            [{"role": "user", "content": f"ANSWER:\n{answer}"}],
        )
        clean = re.sub(r"```[a-z]*", "", gen_questions_raw).strip().strip("`")
        gen_questions = json.loads(clean)
    except Exception:
        return 0.0

    gen_vecs = embedder.encode(gen_questions)
    sims = [
        float(np.dot(orig_vec, v) / (np.linalg.norm(orig_vec) * np.linalg.norm(v) + 1e-9))
        for v in gen_vecs
    ]
    return float(np.mean(sims))


def score_transcript(transcript: dict) -> dict:
    answer   = transcript["hidden_direct_answer"]
    context  = transcript["retrieved_context"]
    question = transcript["question"]

    claims        = extract_claims(answer)
    verifications = [verify_claim(c, context) for c in claims]
    supported     = sum(1 for v in verifications if v["supported"])
    total         = len(claims)
    faithfulness  = supported / total if total else 0.0
    relevance     = answer_relevance(answer, question)

    return {
        "id"              : transcript["id"],
        "question"        : question,
        "n_claims"        : total,
        "n_supported"     : supported,
        "faithfulness"    : round(faithfulness, 3),
        "answer_relevance": round(relevance, 3),
        "claims"          : [
            {"claim": c, "supported": v["supported"], "reason": v["reason"]}
            for c, v in zip(claims, verifications)
        ],
    }


def run_ragas_eval(transcripts: list[dict]) -> dict:
    """
    Args:
        transcripts: list of dicts, each with keys:
            id, question, hidden_direct_answer, retrieved_context
    """
    EVAL_OUTPUT_DIR.mkdir(exist_ok=True)
    results = []

    for t in transcripts:
        print(f"Scoring {t['id']}…")
        results.append(score_transcript(t))

    mean_faith = float(np.mean([r["faithfulness"]     for r in results]))
    mean_relev = float(np.mean([r["answer_relevance"] for r in results]))

    print(f"\nMean Faithfulness:     {mean_faith:.3f}")
    print(f"Mean Answer Relevance: {mean_relev:.3f}")

    out_path = EVAL_OUTPUT_DIR / "ragas_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"✓ Saved to {out_path}")

    return {
        "aggregate": {"mean_faithfulness": mean_faith, "mean_answer_relevance": mean_relev},
        "per_transcript": results,
    }
