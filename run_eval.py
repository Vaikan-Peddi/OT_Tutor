"""
run_eval.py — run all evaluations.

Usage:
    python run_eval.py              # no-op (add a flag)
    python run_eval.py --retrieval  # retrieval quality eval
    python run_eval.py --ragas      # RAGAS faithfulness + relevance (needs eval_transcripts.json)
    python run_eval.py --purity     # Socratic Purity eval (needs eval_transcripts.json)
    python run_eval.py --summary    # print saved results from all completed evals

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


def _load_transcripts(path: Path) -> list:
    with open(path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval", action="store_true", help="Run retrieval quality eval")
    parser.add_argument("--ragas",     action="store_true", help="Run RAGAS faithfulness + relevance eval")
    parser.add_argument("--purity",    action="store_true", help="Run Socratic Purity eval")
    parser.add_argument("--summary",   action="store_true", help="Print saved results from all completed evals")

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


if __name__ == "__main__":
    main()
