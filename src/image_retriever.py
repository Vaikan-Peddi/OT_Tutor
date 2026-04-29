"""
image_retriever.py — match VLM-extracted labels against stored anatomical diagram metadata.

Stored diagrams live in data/images/*.json — one JSON metadata file per diagram image.

Matching strategy:
  - Flatten each stored diagram's metadata (title, structures, labels, region, topic) into a string
  - Embed it with the same sentence-transformer used for text RAG
  - Compare cosine similarity against the VLM-extracted labels query
  - Return the best match if it meets IMAGE_MATCH_THRESHOLD

Metadata JSON format (data/images/<name>.json):
  {
    "filename":       "brachial_plexus.png",
    "title":          "Brachial Plexus Diagram",
    "structures":     ["C5 nerve root", "upper trunk", "median nerve", ...],
    "labels":         ["brachial plexus", "trunks", "terminal branches"],
    "region":         "upper limb",
    "topic":          "brachial plexus anatomy",
    "description":    "Factual 2-3 sentence description of the diagram.",
    "clinical_notes": "Key clinical pearls / injury patterns."
  }
"""

import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

from src.config import IMAGES_DIR, EMBEDDING_MODEL, IMAGE_MATCH_THRESHOLD

_embedder: SentenceTransformer | None = None
_metadata_cache: list[dict] | None = None
_embedding_cache: dict[str, np.ndarray] = {}   # json_path → embedding

_STOPWORDS = {
    "the", "a", "an", "of", "and", "in", "on", "at", "to", "is", "are",
    "for", "with", "by", "from", "as", "its", "this", "that", "into",
    "showing", "shown", "diagram",
}


# ── Lazy loaders ──────────────────────────────────────────────────────────────

def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def _load_all_metadata() -> list[dict]:
    """Load every *.json from data/images/ once, then cache."""
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []

    for json_path in sorted(Path(IMAGES_DIR).glob("*.json")):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_json_path"] = str(json_path)
            records.append(data)
        except Exception as exc:
            print(f"[image_retriever] Skipping {json_path.name}: {exc}")

    _metadata_cache = records
    print(f"[image_retriever] Loaded {len(records)} stored diagram(s) from {IMAGES_DIR}")
    return records


# ── Helpers ───────────────────────────────────────────────────────────────────

def _flatten_metadata(meta: dict) -> str:
    """Flatten a metadata record into a single searchable string."""
    parts: list[str] = []
    for key in ("title", "topic", "region"):
        if meta.get(key):
            parts.append(str(meta[key]))
    for key in ("structures", "labels"):
        if isinstance(meta.get(key), list):
            parts.extend(meta[key])
    if meta.get("description"):
        parts.append(meta["description"])
    return " ".join(parts)


def _get_or_embed(meta: dict) -> np.ndarray:
    """Return a cached embedding for this metadata record (compute once)."""
    key = meta.get("_json_path", id(meta))
    if key not in _embedding_cache:
        text = _flatten_metadata(meta)
        _embedding_cache[key] = _get_embedder().encode([text])[0]
    return _embedding_cache[key]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 1e-8 else 0.0


def _keyword_overlap(query_labels: list[str], topic: str, meta: dict) -> float:
    """
    Jaccard-like keyword overlap: fraction of query terms found in stored metadata.
    Used as a secondary signal alongside cosine similarity.
    """
    query_terms = {
        w.lower()
        for token in (query_labels + [topic])
        for w in token.split()
        if w.lower() not in _STOPWORDS and len(w) > 2
    }
    stored_terms: set[str] = set()
    for key in ("title", "topic", "region"):
        if meta.get(key):
            stored_terms.update(
                w.lower() for w in str(meta[key]).split()
                if w.lower() not in _STOPWORDS and len(w) > 2
            )
    for key in ("structures", "labels"):
        for item in meta.get(key, []):
            stored_terms.update(
                w.lower() for w in item.split()
                if w.lower() not in _STOPWORDS and len(w) > 2
            )
    if not query_terms:
        return 0.0
    return len(query_terms & stored_terms) / len(query_terms)


# ── Public API ────────────────────────────────────────────────────────────────

def find_matching_diagram(labels: list[str], topic: str) -> dict | None:
    """
    Given VLM-extracted labels + topic string, search stored diagram metadata.

    Scoring: 70 % cosine similarity + 30 % keyword overlap.
    Returns the best match if combined score ≥ IMAGE_MATCH_THRESHOLD, else None.

    Args:
        labels: list of anatomical structure names / visible labels from Gemini
        topic:  2-5 word topic string from Gemini (e.g. "brachial plexus anatomy")
    """
    all_metadata = _load_all_metadata()
    if not all_metadata:
        return None

    query_str = " ".join(labels) + " " + topic
    query_emb = _get_embedder().encode([query_str])[0]

    best_score = -1.0
    best_meta: dict | None = None

    for meta in all_metadata:
        cos   = _cosine(query_emb, _get_or_embed(meta))
        kw    = _keyword_overlap(labels, topic, meta)
        score = 0.7 * cos + 0.3 * kw
        if score > best_score:
            best_score = score
            best_meta = meta

    filename = best_meta.get("filename", "?") if best_meta else "?"
    if best_score >= IMAGE_MATCH_THRESHOLD:
        print(f"[image_retriever] Match: '{filename}' (score={best_score:.3f})")
        return best_meta

    print(f"[image_retriever] No match (best={best_score:.3f} < threshold={IMAGE_MATCH_THRESHOLD})")
    return None


def invalidate_cache() -> None:
    """Force reload of metadata on next call (use if you add new JSONs at runtime)."""
    global _metadata_cache
    _metadata_cache = None
    _embedding_cache.clear()
