"""
eval/retrieval_eval.py — 15-question retrieval quality evaluation.
"""

import json
import re
import time

import numpy as np

from src.retriever import retrieve_context
from src.llm import llm_chat
from src.config import EVAL_OUTPUT_DIR

RETRIEVAL_EVAL_QS = [
    # Ch. 11: Muscular System
    {"id": "r01_rotator_cuff",    "chapter": "Ch. 11 – Muscular",
     "question": "Which muscles make up the rotator cuff and what is their shared function?",
     "gold_key_terms": ["supraspinatus", "infraspinatus", "teres minor", "subscapularis", "glenohumeral", "stabilize"],
     "gold_answer_hint": "SITS muscles stabilise the glenohumeral joint"},
    {"id": "r02_thenar_muscles",  "chapter": "Ch. 11 – Muscular",
     "question": "What are the thenar muscles and what movements do they produce at the thumb?",
     "gold_key_terms": ["thenar", "abductor pollicis", "opponens pollicis", "flexor pollicis brevis", "opposition"],
     "gold_answer_hint": "Thenar eminence muscles: abductor/flexor/opponens pollicis brevis"},
    {"id": "r03_wrist_extensors", "chapter": "Ch. 11 – Muscular",
     "question": "Which muscles extend the wrist and what nerve innervates them?",
     "gold_key_terms": ["extensor carpi radialis", "extensor carpi ulnaris", "radial nerve", "posterior interosseous"],
     "gold_answer_hint": "ECRL, ECRB, ECU innervated by radial/posterior interosseous nerve"},
    # Ch. 13: PNS
    {"id": "r04_ulnar_nerve",     "chapter": "Ch. 13 – PNS",
     "question": "What is the function of the ulnar nerve?",
     "gold_key_terms": ["ulnar nerve", "flexor carpi ulnaris", "intrinsic", "C8", "T1", "medial"],
     "gold_answer_hint": "Ulnar n. innervates FCU, medial FDP, most intrinsic hand muscles"},
    {"id": "r05_radial_nerve_palsy", "chapter": "Ch. 13 – PNS",
     "question": "What happens clinically when the radial nerve is damaged at the humerus?",
     "gold_key_terms": ["wrist drop", "radial nerve", "extensor", "humerus", "spiral groove"],
     "gold_answer_hint": "Wrist drop from loss of wrist/finger extensors"},
    {"id": "r06_median_nerve",    "chapter": "Ch. 13 – PNS",
     "question": "Which structures does the median nerve innervate in the hand?",
     "gold_key_terms": ["median nerve", "thenar", "first two lumbricals", "carpal tunnel", "LOAF"],
     "gold_answer_hint": "LOAF muscles + lateral 3.5 digits sensation"},
    {"id": "r07_brachial_plexus", "chapter": "Ch. 13 – PNS",
     "question": "What are the five terminal branches of the brachial plexus?",
     "gold_key_terms": ["musculocutaneous", "axillary", "radial", "median", "ulnar", "brachial plexus"],
     "gold_answer_hint": "Musculocutaneous, axillary, radial, median, ulnar"},
    # Ch. 14: Brain
    {"id": "r08_cerebellum",      "chapter": "Ch. 14 – Brain",
     "question": "What is the primary function of the cerebellum?",
     "gold_key_terms": ["cerebellum", "coordination", "balance", "posture", "motor"],
     "gold_answer_hint": "Coordinates voluntary movement, maintains balance/posture"},
    {"id": "r09_corticospinal",   "chapter": "Ch. 14 – Brain",
     "question": "What is the role of the corticospinal tract in voluntary movement?",
     "gold_key_terms": ["corticospinal", "motor cortex", "pyramidal", "decussation", "voluntary"],
     "gold_answer_hint": "Primary motor pathway: cortex → decussates → spinal motor neurons"},
    {"id": "r10_basal_ganglia",   "chapter": "Ch. 14 – Brain",
     "question": "How do the basal ganglia contribute to motor control?",
     "gold_key_terms": ["basal ganglia", "striatum", "dopamine", "motor control", "caudate", "putamen"],
     "gold_answer_hint": "Modulate movement initiation/suppression via dopaminergic pathways"},
    # Ch. 9: Joints
    {"id": "r11_glenohumeral",    "chapter": "Ch. 9 – Joints",
     "question": "What type of joint is the glenohumeral joint and what movements does it allow?",
     "gold_key_terms": ["glenohumeral", "ball and socket", "flexion", "abduction", "rotation", "synovial"],
     "gold_answer_hint": "Ball-and-socket synovial joint; flexion, extension, abduction, rotation"},
    {"id": "r12_carpal_tunnel",   "chapter": "Ch. 9 – Joints",
     "question": "What passes through the carpal tunnel and what is compressed in CTS?",
     "gold_key_terms": ["carpal tunnel", "median nerve", "flexor tendons", "transverse carpal ligament", "CTS"],
     "gold_answer_hint": "Median nerve + 9 flexor tendons; median nerve compressed in CTS"},
    # Ch. 16: Neurological
    {"id": "r13_upper_motor_neuron", "chapter": "Ch. 16 – Neurological",
     "question": "What are the clinical signs of an upper motor neuron lesion?",
     "gold_key_terms": ["upper motor neuron", "spasticity", "hyperreflexia", "Babinski", "weakness"],
     "gold_answer_hint": "Spasticity, hyperreflexia, positive Babinski, weakness"},
    {"id": "r14_dermatomes",      "chapter": "Ch. 16 – Neurological",
     "question": "What is a dermatome and why is it clinically relevant for OT?",
     "gold_key_terms": ["dermatome", "spinal nerve", "sensory", "C6", "C7", "T1"],
     "gold_answer_hint": "Skin area innervated by single spinal nerve root; maps nerve injury level"},
    {"id": "r15_spinal_tracts",   "chapter": "Ch. 16 – Neurological",
     "question": "What are the main ascending and descending spinal cord tracts and their functions?",
     "gold_key_terms": ["dorsal column", "spinothalamic", "corticospinal", "sensory", "motor", "decussation"],
     "gold_answer_hint": "Dorsal column (fine touch/proprioception), spinothalamic (pain/temp), corticospinal (voluntary motor)"},
]

JUDGE_SYSTEM = """\
You are a strict retrieval quality judge for a medical RAG system.
Given a student question, a gold answer hint, and retrieved context,
decide whether the context contains enough information to derive the gold answer.
Output ONLY valid JSON — no preamble, no markdown fences:
{
  "verdict": "FULL" | "PARTIAL" | "MISS",
  "reason": "One sentence explaining what is present or missing."
}
"""


def keyterm_hit_rate(context: str, key_terms: list) -> tuple:
    ctx = context.lower()
    hits   = [t for t in key_terms if t.lower() in ctx]
    misses = [t for t in key_terms if t.lower() not in ctx]
    rate   = len(hits) / len(key_terms) if key_terms else 0.0
    return rate, hits, misses


def llm_judge(question: str, gold_hint: str, context: str) -> dict:
    msg = f"QUESTION: {question}\n\nGOLD ANSWER HINT: {gold_hint}\n\nRETRIEVED CONTEXT:\n{context}"
    try:
        raw   = llm_chat(JUDGE_SYSTEM, [{"role": "user", "content": msg}])
        clean = re.sub(r"```[a-z]*", "", raw).strip().strip("`").strip()
        return json.loads(clean)
    except Exception as e:
        return {"verdict": "PARSE_ERROR", "reason": str(e)[:120]}


def run_retrieval_eval() -> dict:
    EVAL_OUTPUT_DIR.mkdir(exist_ok=True)
    results = []

    for i, q in enumerate(RETRIEVAL_EVAL_QS, 1):
        print(f"[{i:02d}/15] {q['id']}")
        ctx, srcs = retrieve_context(q["question"], k=3)
        pages = [s.get("page", "?") for s in srcs]
        kt_rate, hits, misses = keyterm_hit_rate(ctx, q["gold_key_terms"])
        judge   = llm_judge(q["question"], q["gold_answer_hint"], ctx)
        verdict = judge.get("verdict", "PARSE_ERROR")
        sym     = {"FULL": "✅", "PARTIAL": "⚠️", "MISS": "❌"}.get(verdict, "💥")
        print(f"  pages={pages}  kt={kt_rate:.2f}  {sym} {verdict}")
        print(f"  {judge.get('reason', '')[:90]}")
        results.append({
            "id": q["id"], "chapter": q["chapter"], "question": q["question"],
            "pages": pages, "kt_rate": round(kt_rate, 3),
            "kt_hits": hits, "kt_misses": misses,
            "verdict": verdict, "reason": judge.get("reason", ""),
            "context": ctx,
        })
        time.sleep(0.4)

    verdicts   = [r["verdict"] for r in results]
    n_full, n_partial, n_miss = verdicts.count("FULL"), verdicts.count("PARTIAL"), verdicts.count("MISS")
    n_total    = len(results)
    mean_kt    = np.mean([r["kt_rate"] for r in results])
    gold_in    = n_full + n_partial

    print(f"\nFULL: {n_full}/{n_total}  PARTIAL: {n_partial}/{n_total}  MISS: {n_miss}/{n_total}")
    print(f"Gold-in-context: {gold_in}/{n_total} ({100*gold_in/n_total:.0f}%)  Mean KT: {mean_kt:.3f}")

    out = {
        "aggregate": {
            "n_total": n_total, "n_full": n_full, "n_partial": n_partial,
            "n_miss": n_miss, "gold_in_context_pct": round(100*gold_in/n_total, 1),
            "mean_key_term_rate": round(float(mean_kt), 3),
        },
        "per_question": results,
    }
    out_path = EVAL_OUTPUT_DIR / "retrieval_quality_results.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"✓ Saved to {out_path}")
    return out
