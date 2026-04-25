"""
run_eval.py — run all evaluations.

Usage:
    python run_eval.py              # retrieval eval only (no transcripts needed)
    python run_eval.py --ragas      # also run RAGAS (requires eval_transcripts.json)

eval_transcripts.json format:
[
  {
    "id": "session_abc",
    "question": "What is the function of the ulnar nerve?",
    "hidden_direct_answer": "...",
    "retrieved_context": "..."
  },
  ...
]
"""

import argparse
import json
from pathlib import Path

from src.eval.retrieval_eval import run_retrieval_eval
from src.eval.ragas_eval import run_ragas_eval


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ragas", action="store_true", help="Also run RAGAS faithfulness eval")
    args = parser.parse_args()

    print("\n── Retrieval Quality Eval ─────────────────────────────────────")
    run_retrieval_eval()

    if args.ragas:
        transcripts_path = Path("eval_transcripts.json")
        if not transcripts_path.exists():
            print("\n[RAGAS] eval_transcripts.json not found — skipping RAGAS eval.")
            print("  Export session transcripts from your tutor runs and save as eval_transcripts.json.")
        else:
            with open(transcripts_path) as f:
                transcripts = json.load(f)
            print(f"\n── RAGAS Eval ({len(transcripts)} transcripts) ─────────────────────────")
            run_ragas_eval(transcripts)


if __name__ == "__main__":
    main()
