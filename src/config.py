"""
Central config — all paths, model settings, and env vars live here.
Edit this file instead of hunting through the codebase.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).resolve().parent.parent
DATA_DIR   = ROOT_DIR / "data"
DB_DIR     = ROOT_DIR / "db"
PDF_PATH   = DATA_DIR / "openstax_anatomy.pdf"
CHROMA_PATH = str(DB_DIR / "chroma_db")

# ── ChromaDB ───────────────────────────────────────────────────────────────
COLLECTION_NAME = "ot_knowledge_base"

# ── Embedding model ────────────────────────────────────────────────────────
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ── LLM provider ──────────────────────────────────────────────────────────
# Switch by changing ACTIVE_PROVIDER. Add API keys to .env
ACTIVE_PROVIDER = os.getenv("ACTIVE_PROVIDER", "groq")
ACTIVE_MODEL    = os.getenv("ACTIVE_MODEL",    "llama-3.1-8b-instant")

GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Chunking ───────────────────────────────────────────────────────────────
CHUNK_SIZE    = 512
CHUNK_OVERLAP = 50

# ── Retrieval ──────────────────────────────────────────────────────────────
DEFAULT_K = 4          # top-k passages per query

# ── Session / tutoring ─────────────────────────────────────────────────────
REVEAL_TURN_THRESHOLD = 4   # /reveal unlocks after this many turns
MAX_TOKENS_LLM        = 2048

# ── Eval ───────────────────────────────────────────────────────────────────
EVAL_OUTPUT_DIR = ROOT_DIR / "eval_results"

# ── Vision / Multimodal ───────────────────────────────────────────────────────
GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY", "")
VISION_MODEL          = os.getenv("VISION_MODEL", "gemini-2.5-flash")
IMAGES_DIR            = DATA_DIR / "images_json"   # JSON metadata files
IMAGES_PICS_DIR       = DATA_DIR / "images"        # actual diagram image files
IMAGE_MATCH_THRESHOLD = float(os.getenv("IMAGE_MATCH_THRESHOLD", "0.55"))
