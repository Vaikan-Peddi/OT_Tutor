"""
retriever.py — loads ChromaDB + embedder once (lazy) and exposes retrieve_context().
"""

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import CHROMA_PATH, COLLECTION_NAME, EMBEDDING_MODEL, DEFAULT_K

_client     = None
_collection = None
_embedder   = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client     = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_collection(COLLECTION_NAME)
        print(f"[retriever] ChromaDB loaded — {_collection.count()} chunks available.")
    return _collection


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def retrieve_context(question: str, k: int = DEFAULT_K) -> tuple[str, list[dict]]:
    """
    Query ChromaDB for the top-k chunks most relevant to `question`.

    Returns:
        context_str : chunks joined as a single string → fed to LLM
        sources     : list of metadata dicts → used for citations
    """
    if k == 0:
        return "", []

    collection = _get_collection()
    embedder   = _get_embedder()

    query_embedding = embedder.encode([question])
    results = collection.query(query_embeddings=query_embedding, n_results=k)

    chunks    = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_str = "\n\n---\n\n".join(
        f"[Passage {i+1} | Page {meta['page']}]\n{chunk}"
        for i, (chunk, meta) in enumerate(zip(chunks, metadatas))
    )

    return context_str, metadatas
