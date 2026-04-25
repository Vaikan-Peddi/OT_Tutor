"""
ingest.py — one-time pipeline: PDF → chunks → embeddings → ChromaDB.

Run via:  python run_ingest.py
"""

import re
import fitz                          # PyMuPDF
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import (
    PDF_PATH, CHROMA_PATH, COLLECTION_NAME,
    EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP
)


# ── Text utilities ─────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\n ', '\n')
    return text.strip()


# ── PDF extraction ─────────────────────────────────────────────────────────

def extract_pages(pdf_path: str) -> list[dict]:
    """Return list of {text, page} dicts for pages with >100 chars of content."""
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        text = clean_text(doc[page_num].get_text("text"))
        if len(text) > 100:
            pages.append({"text": text, "page": page_num + 1})
    print(f"[ingest] Extracted text from {len(pages)} pages.")
    return pages


# ── Chunking ───────────────────────────────────────────────────────────────

def chunk_pages(pages: list[dict]) -> tuple[list[str], list[dict], list[str]]:
    """Split pages into overlapping chunks. Returns (texts, metadatas, ids)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " "],
    )
    chunks, metadatas, ids = [], [], []
    for page in pages:
        for i, chunk in enumerate(splitter.split_text(page["text"])):
            chunk_id = f"page{page['page']}_chunk{i}"
            chunks.append(chunk)
            ids.append(chunk_id)
            metadatas.append({
                "source":   "OpenStax_A&P_2e",
                "page":     str(page["page"]),
                "chunk_id": chunk_id,
            })
    print(f"[ingest] Created {len(chunks)} chunks.")
    return chunks, metadatas, ids


# ── Embedding ──────────────────────────────────────────────────────────────

def embed_chunks(chunks: list[str]) -> list:
    embedder = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = embedder.encode(chunks, batch_size=64, show_progress_bar=True)
    print(f"[ingest] Embeddings shape: {len(embeddings)} × {len(embeddings[0])}")
    return embeddings


# ── ChromaDB ───────────────────────────────────────────────────────────────

def build_chromadb(chunks, metadatas, ids, embeddings, batch_size: int = 1000):
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    # Wipe and recreate (idempotent re-ingest)
    try:
        client.delete_collection(COLLECTION_NAME)
        print("[ingest] Deleted existing collection.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    for i in range(0, len(chunks), batch_size):
        collection.add(
            documents  = chunks[i:i + batch_size],
            embeddings = embeddings[i:i + batch_size],
            metadatas  = metadatas[i:i + batch_size],
            ids        = ids[i:i + batch_size],
        )
        print(f"[ingest] Stored batch {i // batch_size + 1}")

    print(f"[ingest] ChromaDB ready at {CHROMA_PATH} — {collection.count()} documents.")
    return collection


# ── Main ───────────────────────────────────────────────────────────────────

def run_ingest():
    if not PDF_PATH.exists():
        raise FileNotFoundError(
            f"PDF not found at {PDF_PATH}\n"
            "Place openstax_anatomy.pdf in the data/ directory and re-run."
        )

    pages               = extract_pages(str(PDF_PATH))
    chunks, metas, ids  = chunk_pages(pages)
    embeddings          = embed_chunks(chunks)
    build_chromadb(chunks, metas, ids, embeddings)
