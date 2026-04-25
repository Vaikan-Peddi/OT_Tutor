"""
run_ingest.py — one-time script to build the local ChromaDB from the PDF.

Run ONCE before starting the tutor:
    python run_ingest.py

After this completes, db/chroma_db/ is populated and persists across runs.
Re-run only if you swap the PDF.
"""

from src.ingest import run_ingest

if __name__ == "__main__":
    run_ingest()
