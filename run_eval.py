"""
run_eval.py — run all evaluations.

Usage:
    python run_eval.py              # no-op (add a flag)
    python run_eval.py --retrieval  # retrieval quality eval
    python run_eval.py --ragas      # RAGAS faithfulness + relevance (needs eval_transcripts.json)
    python run_eval.py --purity     # Socratic Purity eval (needs eval_transcripts.json)
    python run_eval.py --multimodal      # blind-test multimodal structure identification eval
    python run_eval.py --generalizability # Physics subject-swap generalizability eval
    python run_eval.py --summary          # print saved results from all completed evals

eval_results/eval_transcripts.json format:
[
  {
    "id": "session_abc",
    "question": "What is the function of the ulnar nerve?",
    "hidden_direct_answer": "...",
    "retrieved_context": "...",
    "conversations": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."}
    ]
  },
  ...
]
"""

import argparse
import json
from pathlib import Path

from src.eval.retrieval_eval import run_retrieval_eval
from src.eval.ragas_eval import run_ragas_eval
from src.eval.socratic_purity_eval import run_socratic_purity_eval
from src.eval.multimodal_eval import run_multimodal_eval
from src.eval.generalizability_eval import run_generalizability_eval


def _load_transcripts(path: Path) -> list:
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval",  action="store_true", help="Run retrieval quality eval")
    parser.add_argument("--ragas",      action="store_true", help="Run RAGAS faithfulness + relevance eval")
    parser.add_argument("--purity",     action="store_true", help="Run Socratic Purity eval")
    parser.add_argument("--multimodal",       action="store_true", help="Run blind-test multimodal structure identification eval")
    parser.add_argument("--generalizability", action="store_true", help="Run Physics subject-swap generalizability eval")
    parser.add_argument("--summary",          action="store_true", help="Print saved results from all completed evals")

    args = parser.parse_args()

    # ── Summary: read saved JSON files, print means ────────────────────────
    if args.summary:
        ragas_path   = Path("eval_results/ragas_results.json")
        purity_path  = Path("eval_results/socratic_purity_results.json")

        if ragas_path.exists():
            results    = json.loads(ragas_path.read_text())
            mean_faith = sum(r["faithfulness"]     for r in results) / len(results)
            mean_relev = sum(r["answer_relevance"] for r in results) / len(results)
            print(f"\n── RAGAS Summary ({len(results)} transcripts) ──────────────────────────")
            print(f"  Mean Faithfulness:     {mean_faith:.3f}")
            print(f"  Mean Answer Relevance: {mean_relev:.3f}")
            print()
            for r in results:
                print(f"  {r['id']}  faith={r['faithfulness']:.3f}  relev={r['answer_relevance']:.3f}  {r['question'][:55]}")
        else:
            print("ragas_results.json not found — run with --ragas first.")

        if purity_path.exists():
            results = json.loads(purity_path.read_text())
            valid   = [r for r in results if r.get("purity_score") is not None]
            mean_purity = sum(r["purity_score"]    for r in valid) / len(valid)
            leak_rate   = sum(1 for r in valid if r["keyword_leaked"]) / len(valid)
            print(f"\n── Socratic Purity Summary ({len(valid)} transcripts) ──────────────────")
            print(f"  Mean Purity Score:   {mean_purity:.3f}  (1.0 = fully Socratic)")
            print(f"  Keyword Leak Rate:   {leak_rate:.3f}  (fraction with answer term in hints)")
            print()
            for r in valid:
                tag = "LEAKED" if r["keyword_leaked"] else "clean "
                print(f"  {r['id']}  purity={r['purity_score']:.3f}  [{tag}]  {r['question'][:50]}")
        else:
            print("\nsocratic_purity_results.json not found — run with --purity first.")

        mm_path = Path("eval_results/multimodal_eval_results.json")
        if mm_path.exists():
            data = json.loads(mm_path.read_text())
            agg  = data.get("aggregate", {})
            imgs = data.get("per_image", [])
            print(f"\n── Multimodal Eval Summary ({agg.get('n_images', len(imgs))} image(s)) ──────────────────────")
            print(f"  Mean Structure F1:      {agg.get('mean_structure_f1', 0):.3f}")
            print(f"  Mean Precision:         {agg.get('mean_precision', 0):.3f}")
            print(f"  Mean Recall:            {agg.get('mean_recall', 0):.3f}")
            print(f"  Diagram Match Rate:     {agg.get('diagram_match_rate', 0):.3f}")
            print(f"  Region Accuracy:        {agg.get('region_accuracy', 0):.3f}")
            print(f"  Confidence dist:        {agg.get('confidence_dist', {})}")
            print()
            for r in imgs:
                f1  = r["structure_f1"]["f1"]
                ok  = "✓" if r["diagram_match"] else "✗"
                reg = "✓" if r["region_correct"] else "✗"
                print(f"  {r['image']:<40}  F1={f1:.3f}  match={ok}  region={reg}  conf={r['gemini_confidence']}")
        else:
            print("\nmultimodal_eval_results.json not found — run with --multimodal first.")

        gen_path = Path("eval_results/generalizability_results.json")
        if gen_path.exists():
            data = json.loads(gen_path.read_text())
            agg  = data.get("aggregate", {})
            print(f"\n── Generalizability Summary (subject: {data.get('subject', '?')}) ────────────────")
            print(f"  Corpus chunks:          {data.get('corpus_chunks', '?')}")
            print(f"  Gold-in-context:        {agg.get('gold_in_context_pct', 0):.1f}%  "
                  f"(FULL={agg.get('n_full',0)}  PARTIAL={agg.get('n_partial',0)}  MISS={agg.get('n_miss',0)})")
            print(f"  Mean Key-Term Rate:     {agg.get('mean_key_term_rate', 0):.3f}")
            print(f"  Verdict: {data.get('generalisation_verdict', '')}")
            pt = data.get("per_topic", {})
            if pt:
                print()
                for topic, v in pt.items():
                    print(f"  {topic:30s}  FULL={v['n_full']} PARTIAL={v['n_partial']} "
                          f"MISS={v['n_miss']} avg_kt={v['avg_kt']:.2f}")
        else:
            print("\ngeneralizability_results.json not found — run with --generalizability first.")

        return

    # ── Active eval runs ───────────────────────────────────────────────────
    if args.retrieval:
        print("\n── Retrieval Quality Eval ─────────────────────────────────────")
        run_retrieval_eval()

    transcripts_path = Path("eval_results/eval_transcripts.json")

    if args.ragas:
        if not transcripts_path.exists():
            print("\n[RAGAS] eval_transcripts.json not found.")
        else:
            transcripts = _load_transcripts(transcripts_path)
            print(f"\n── RAGAS Eval ({len(transcripts)} transcripts) ─────────────────────────")
            run_ragas_eval(transcripts)

    if args.purity:
        if not transcripts_path.exists():
            print("\n[Purity] eval_transcripts.json not found.")
        else:
            transcripts = _load_transcripts(transcripts_path)
            print(f"\n── Socratic Purity Eval ({len(transcripts)} transcripts) ───────────────")
            run_socratic_purity_eval(transcripts)

    if args.multimodal:
        print("\n── Multimodal Blind-Test Eval ──────────────────────────────────────")
        run_multimodal_eval()

    if args.generalizability:
        print("\n── Generalizability Eval (Physics subject swap) ────────────────────")
        run_generalizability_eval()


if __name__ == "__main__":
    main()
