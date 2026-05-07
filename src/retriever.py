"""
retriever.py — loads ChromaDB once (lazy) and exposes retrieve_context().
Embedding is handled by ChromaDB's built-in ONNX runtime (no torch needed).
"""

import chromadb

from src.config import CHROMA_PATH, COLLECTION_NAME, DEFAULT_K

_client     = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client     = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _client.get_collection(COLLECTION_NAME)
        print(f"[retriever] ChromaDB loaded — {_collection.count()} chunks available.")
    return _collection


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
    results = collection.query(query_texts=[question], n_results=k)

    chunks    = results["documents"][0]
    metadatas = results["metadatas"][0]

    context_str = "\n\n---\n\n".join(
        f"[Passage {i+1} | Page {meta['page']}]\n{chunk}"
        for i, (chunk, meta) in enumerate(zip(chunks, metadatas))
    )

    return context_str, metadatas
