"""
agents/vision.py — Gemini Vision pipeline for multimodal diagram tutoring.

Full pipeline (called once per image session, on turn 1):

  Step 1 — Gemini Vision extracts structured anatomy info from the uploaded image:
              { identified_structures, labels_visible, region, topic, description, confidence }

  Step 2 — image_retriever searches data/images/*.json for a matching stored diagram.
              Match found  → stored metadata is the authoritative ground truth context.
              No match     → Gemini's own description is used as context (VLM-grounded).

  Step 3 — RAG augmentation: retrieve_context() fetches textbook passages for the topic.

  Step 4 — Combine both contexts (image ground truth + textbook RAG).

  Step 5 — run_initializer() receives the combined context and generates the standard
              session init dict: { direct_answer, clinical_scenario, related_questions,
              useful_info, topic_label }.

The output dict is a drop-in replacement for run_initializer() output, so the rest of the
Socratic tutoring flow (tutor.py, analyzer.py, mastery.py) runs unchanged.

SDK: google-generativeai  — `pip install google-generativeai Pillow`
"""

import io
import json
import re

import PIL.Image
import google.generativeai as genai

from src.config import GEMINI_API_KEY, VISION_MODEL
from src.image_retriever import find_matching_diagram
from src.retriever import retrieve_context
from src.agents.analyzer import run_initializer


# ── Gemini extraction prompt ──────────────────────────────────────────────────

_VISION_SYSTEM = """\
You are an expert anatomist analyzing a medical or anatomical diagram for an OT tutoring system.

Examine the image carefully and return ONLY a valid JSON object — no markdown, no prose.

JSON schema:
{
  "identified_structures": ["list every anatomical structure you can identify"],
  "labels_visible":        ["any text labels printed directly on the diagram"],
  "region":                "body region shown (e.g. upper limb, brain, thorax)",
  "topic":                 "main anatomical topic in 2-5 words, lowercase",
  "description":           "2-3 sentences: factual description of what the diagram shows",
  "confidence":            "high | medium | low"
}

Rules:
- Use precise anatomical terminology.
- List every structure visible, even partially.
- description must be factual and grounded in what you see — no guessing.
- If the image is NOT an anatomical diagram, set confidence to "low" and describe what you see.
- Output ONLY the JSON object.
"""

_VISION_FALLBACK = {
    "identified_structures": [],
    "labels_visible":        [],
    "region":                "unknown",
    "topic":                 "anatomy diagram",
    "description":           "Could not extract information from the image.",
    "confidence":            "low",
}


# ── Gemini Vision call ────────────────────────────────────────────────────────

def _call_gemini_vision(image_bytes: bytes, mime_type: str, student_question: str = "") -> dict:
    """
    Send the image to Gemini Vision and return parsed anatomy extraction dict.
    Uses google-generativeai SDK with gemini-2.5-flash.
    Falls back to _VISION_FALLBACK on any error.
    """
    if not GEMINI_API_KEY:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Add it to your .env file.\n"
            "Get a free key at: https://aistudio.google.com/app/apikey"
        )

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(VISION_MODEL)
    image = PIL.Image.open(io.BytesIO(image_bytes))

    prompt_parts = [_VISION_SYSTEM]
    if student_question:
        prompt_parts.append(f"\n\nStudent's question about this image: {student_question}")
    prompt_parts.append(image)

    try:
        response = model.generate_content(prompt_parts)
        raw = response.text.strip()
    except Exception as exc:
        print(f"[vision] Gemini API error: {exc}")
        return _VISION_FALLBACK.copy()

    # Parse JSON — same multi-pass strategy as analyzer.py
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    brace = re.search(r"\{[\s\S]*\}", raw)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass

    print(f"[vision] JSON parse failed. Raw response:\n{raw[:400]}")
    return _VISION_FALLBACK.copy()


# ── Context builders ──────────────────────────────────────────────────────────

def _context_from_stored(stored: dict) -> str:
    """Format a stored diagram metadata record as a plain-text context block."""
    lines = ["=== STORED DIAGRAM (authoritative ground truth) ==="]
    if stored.get("title"):
        lines.append(f"Diagram title: {stored['title']}")
    if stored.get("description"):
        lines.append(f"Description: {stored['description']}")
    if stored.get("structures"):
        lines.append(f"Structures shown: {', '.join(stored['structures'])}")
    if stored.get("labels"):
        lines.append(f"Diagram labels: {', '.join(stored['labels'])}")
    if stored.get("region"):
        lines.append(f"Body region: {stored['region']}")
    if stored.get("clinical_notes"):
        lines.append(f"Clinical notes: {stored['clinical_notes']}")
    return "\n".join(lines)


def _context_from_vlm(vlm: dict) -> str:
    """Format VLM extraction output as a plain-text context block."""
    lines = ["=== IMAGE ANALYSIS (Gemini Vision — VLM grounded) ==="]
    if vlm.get("topic"):
        lines.append(f"Topic: {vlm['topic']}")
    if vlm.get("description"):
        lines.append(f"Description: {vlm['description']}")
    if vlm.get("identified_structures"):
        lines.append(f"Identified structures: {', '.join(vlm['identified_structures'])}")
    if vlm.get("labels_visible"):
        lines.append(f"Labels visible in diagram: {', '.join(vlm['labels_visible'])}")
    if vlm.get("region"):
        lines.append(f"Body region: {vlm['region']}")
    lines.append(f"Gemini confidence: {vlm.get('confidence', 'unknown')}")
    return "\n".join(lines)


# ── Public entry point ────────────────────────────────────────────────────────

def run_vision_initializer(
    image_bytes: bytes,
    mime_type: str,
    text_question: str = "",
) -> dict:
    """
    Vision-based session initializer — drop-in replacement for run_initializer().

    Returns the standard init dict:
        direct_answer, clinical_scenario, related_questions, useful_info, topic_label

    Plus vision-specific extras (stored on session by manager.py):
        image_identified_as  : human-readable name of what was identified
        image_source         : "stored" (matched a saved diagram) | "vlm" (Gemini only)
        image_structures     : list of structure names Gemini identified
        image_rag_sources    : RAG metadata dicts (same as normal retrieved_sources)
    """
    # ── Step 1: Gemini Vision extraction ─────────────────────────────────────
    print("[vision] Calling Gemini Vision to analyse image …")
    vlm = _call_gemini_vision(image_bytes, mime_type, text_question)

    identified_structures = vlm.get("identified_structures", [])
    labels_visible        = vlm.get("labels_visible", [])
    topic                 = vlm.get("topic", "anatomy diagram")
    region                = vlm.get("region", "")
    confidence            = vlm.get("confidence", "low")

    print(f"[vision] Identified: '{topic}' | "
          f"{len(identified_structures)} structures | confidence={confidence}")

    # ── Step 2: Try to match a stored diagram ─────────────────────────────────
    all_labels   = identified_structures + labels_visible
    stored_match = find_matching_diagram(all_labels, topic)

    if stored_match:
        image_context    = _context_from_stored(stored_match)
        image_source     = "stored"
        identified_as    = stored_match.get("title", topic)
    else:
        image_context    = _context_from_vlm(vlm)
        image_source     = "vlm"
        identified_as    = topic

    # ── Step 3: RAG augmentation from textbook ────────────────────────────────
    rag_query = text_question if text_question else f"{topic} {region} anatomy".strip()
    rag_context, rag_sources = retrieve_context(rag_query)

    # ── Step 4: Combine contexts ──────────────────────────────────────────────
    combined_context = "\n\n".join(filter(None, [
        image_context,
        "",
        "=== TEXTBOOK PASSAGES (RAG) ===",
        rag_context or "No textbook passages retrieved.",
    ]))

    # ── Step 5: Generate pedagogical content via run_initializer ─────────────
    effective_question = (
        text_question
        or f"What anatomical structures are shown in this diagram of {identified_as}?"
    )
    print(f"[vision] Running initializer with image source='{image_source}' …")
    result = run_initializer(
        original_question=effective_question,
        context=combined_context,
    )

    # Attach vision-specific metadata for the manager / session
    result["image_identified_as"] = identified_as
    result["image_source"]        = image_source
    result["image_structures"]    = identified_structures
    result["image_rag_sources"]   = rag_sources

    print(f"[vision] Initializer result: direct_answer='{result['direct_answer']}' | "
          f"{len(result['related_questions'])} related questions | "
          f"{len(result['useful_info'])} useful info items")

    return result
