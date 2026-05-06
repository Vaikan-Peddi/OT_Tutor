"""
src/eval/multimodal_eval.py — Blind-test multimodal evaluation.

For every image in data/images/ that has a matching ground-truth JSON in
data/images_json/, this module:

  1. Calls Gemini Vision (the "blind test") — model receives only the raw image.
  2. Compares predictions against ground-truth structures / region using:
       - Structure F1  (fuzzy token-overlap matching for each structure)
       - Diagram Match Accuracy  (does image_retriever return the correct record?)
       - Region Accuracy  (partial token-overlap on region string)
  3. Saves per-image results + aggregate metrics to
       eval_results/multimodal_eval_results.json

Adding more images is automatic: drop a new image in data/images/ and its
metadata JSON in data/images_json/ — the next eval run picks them up.

Pairing strategy:
  Primary  — JSON "filename" field → look for that exact file in data/images/
  Fallback — normalise JSON stem (hyphen → underscore, case-fold) and match
             against image stems across all supported extensions.
"""

import json
import time
from pathlib import Path

from src.config import IMAGES_DIR, IMAGES_PICS_DIR
from src.agents.vision import _call_gemini_vision
from src.image_retriever import find_matching_diagram, invalidate_cache

_IMAGES_PICS_DIR = IMAGES_PICS_DIR

_IMG_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

RESULTS_PATH = Path("eval_results/multimodal_eval_results.json")


# ── Image / JSON pairing ───────────────────────────────────────────────────────

def _build_stem_map(image_dir: Path) -> dict[str, Path]:
    """Return {normalised_stem: image_path} for every image in image_dir."""
    stem_map: dict[str, Path] = {}
    for p in image_dir.iterdir():
        if p.suffix.lower() in _IMG_SUFFIXES:
            stem_map[p.stem.replace("-", "_").lower()] = p
    return stem_map


def _pair_images_and_jsons() -> list[tuple[Path, dict]]:
    """
    Match every JSON in data/images_json/ to an image file in data/images/.
    Returns [(image_path, ground_truth_metadata), ...].
    """
    json_dir  = Path(IMAGES_DIR)          # data/images_json/
    image_dir = _IMAGES_PICS_DIR          # data/images/

    if not image_dir.exists():
        print(f"[multimodal_eval] Image directory not found: {image_dir}")
        return []

    stem_map = _build_stem_map(image_dir)
    pairs: list[tuple[Path, dict]] = []

    for json_path in sorted(json_dir.glob("*.json")):
        try:
            meta = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[multimodal_eval] Skipping {json_path.name}: {exc}")
            continue

        img_path: Path | None = None

        # Strategy 1: use "filename" field from the JSON
        if meta.get("filename"):
            candidate = image_dir / meta["filename"]
            if candidate.exists():
                img_path = candidate

        # Strategy 2: stem-based fallback (handles hyphen vs underscore, ext differences)
        if img_path is None:
            norm_stem = json_path.stem.replace("-", "_").lower()
            img_path  = stem_map.get(norm_stem)

        if img_path is None:
            print(f"[multimodal_eval] No image found for {json_path.name} — skipping.")
            continue

        pairs.append((img_path, meta))
        print(f"[multimodal_eval] Paired: {img_path.name}  ↔  {json_path.name}")

    return pairs


# ── Fuzzy structure matching ───────────────────────────────────────────────────

def _tokens(s: str) -> set[str]:
    """Lowercase token set, ignoring very short words."""
    return {w.lower() for w in s.replace("-", " ").split() if len(w) > 1}


def _fuzzy_match(pred: str, gt_list: list[str], threshold: float = 0.5) -> bool:
    """True if pred has Jaccard token-overlap ≥ threshold with any GT string."""
    pred_tok = _tokens(pred)
    if not pred_tok:
        return False
    for gt in gt_list:
        gt_tok = _tokens(gt)
        if not gt_tok:
            continue
        jaccard = len(pred_tok & gt_tok) / len(pred_tok | gt_tok)
        if jaccard >= threshold:
            return True
    return False


def _structure_f1(predicted: list[str], ground_truth: list[str]) -> dict:
    """
    Precision / Recall / F1 between predicted and GT structure lists.

    True-positive definition:
      Precision side — predicted structure fuzzy-matches at least one GT structure.
      Recall    side — GT structure fuzzy-matched by at least one predicted structure.
    """
    if not predicted and not ground_truth:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "tp": 0, "fp": 0, "fn": 0}

    tp_prec = sum(1 for p in predicted  if _fuzzy_match(p, ground_truth))
    tp_rec  = sum(1 for g in ground_truth if _fuzzy_match(g, predicted))

    precision = tp_prec / len(predicted)   if predicted   else 0.0
    recall    = tp_rec  / len(ground_truth) if ground_truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    return {
        "precision": round(precision, 4),
        "recall":    round(recall,    4),
        "f1":        round(f1,        4),
        "tp":        tp_prec,
        "fp":        len(predicted) - tp_prec,
        "fn":        len(ground_truth) - tp_rec,
    }


# ── MIME helper ────────────────────────────────────────────────────────────────

def _mime(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"


# ── Per-image evaluation ───────────────────────────────────────────────────────

def _eval_one(image_path: Path, gt: dict) -> dict:
    """Run Gemini Vision on one image and score against ground truth."""
    print(f"\n[multimodal_eval] Evaluating: {image_path.name}")

    vlm = _call_gemini_vision(image_path.read_bytes(), _mime(image_path))

    pred_structures = vlm.get("identified_structures", [])
    pred_labels     = vlm.get("labels_visible", [])
    pred_region     = vlm.get("region", "").strip().lower()
    pred_topic      = vlm.get("topic",  "").strip().lower()
    confidence      = vlm.get("confidence", "low")

    gt_structures = gt.get("structures", [])
    gt_region     = gt.get("region", "").strip().lower()
    gt_filename   = gt.get("filename", image_path.name)

    # ── Metric 1: Structure F1 ─────────────────────────────────────────────────
    f1_scores = _structure_f1(pred_structures, gt_structures)

    # ── Metric 2: Diagram Match Accuracy ──────────────────────────────────────
    stored = find_matching_diagram(pred_structures + pred_labels, pred_topic)
    matched_correctly = False
    matched_filename  = None
    if stored:
        matched_filename  = stored.get("filename", "")
        matched_correctly = (
            Path(matched_filename).stem.lower() == Path(gt_filename).stem.lower()
        )

    # ── Metric 3: Region Accuracy (partial token overlap ≥ 50 %) ──────────────
    gt_tok   = _tokens(gt_region)
    pred_tok = _tokens(pred_region)
    region_overlap  = len(gt_tok & pred_tok) / len(gt_tok) if gt_tok else 0.0
    region_correct  = region_overlap >= 0.5

    result = {
        "image":              image_path.name,
        "gt_title":           gt.get("title", ""),
        "gt_structures_n":    len(gt_structures),
        "pred_structures_n":  len(pred_structures),
        "structure_f1":       f1_scores,
        "diagram_match":      matched_correctly,
        "matched_filename":   matched_filename,
        "region_correct":     region_correct,
        "gt_region":          gt_region,
        "pred_region":        pred_region,
        "pred_topic":         pred_topic,
        "gemini_confidence":  confidence,
    }

    print(
        f"  F1={f1_scores['f1']:.3f} "
        f"(P={f1_scores['precision']:.3f} R={f1_scores['recall']:.3f})  "
        f"match={'✓' if matched_correctly else '✗'}  "
        f"region={'✓' if region_correct else '✗'}  "
        f"conf={confidence}"
    )
    return result


# ── Public entry point ─────────────────────────────────────────────────────────

def run_multimodal_eval() -> None:
    """
    Blind-test multimodal evaluation across all paired image/JSON files.
    Saves results to eval_results/multimodal_eval_results.json.
    """
    pairs = _pair_images_and_jsons()
    if not pairs:
        print(
            "[multimodal_eval] No image/JSON pairs found.\n"
            "  → Add images to data/images/ and metadata JSONs to data/images_json/."
        )
        return

    n_total = len(pairs)
    print(f"\n[multimodal_eval] {n_total} image(s) found — starting blind-test evaluation …\n")

    # Load the stored-diagram index once (shared across all images)
    invalidate_cache()

    per_image: list[dict] = []
    for img_path, gt_meta in pairs:
        per_image.append(_eval_one(img_path, gt_meta))
        time.sleep(1)   # gentle rate-limit for Gemini API

    # ── Aggregate metrics ──────────────────────────────────────────────────────
    n = len(per_image)
    mean_f1        = sum(r["structure_f1"]["f1"]        for r in per_image) / n
    mean_precision = sum(r["structure_f1"]["precision"] for r in per_image) / n
    mean_recall    = sum(r["structure_f1"]["recall"]    for r in per_image) / n
    match_rate     = sum(1 for r in per_image if r["diagram_match"])  / n
    region_rate    = sum(1 for r in per_image if r["region_correct"]) / n

    conf_dist: dict[str, int] = {}
    for r in per_image:
        c = r["gemini_confidence"]
        conf_dist[c] = conf_dist.get(c, 0) + 1

    aggregate = {
        "n_images":           n,
        "mean_structure_f1":  round(mean_f1,        4),
        "mean_precision":     round(mean_precision, 4),
        "mean_recall":        round(mean_recall,    4),
        "diagram_match_rate": round(match_rate,     4),
        "region_accuracy":    round(region_rate,    4),
        "confidence_dist":    conf_dist,
    }

    output = {"aggregate": aggregate, "per_image": per_image}
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")

    n_match  = sum(1 for r in per_image if r["diagram_match"])
    n_region = sum(1 for r in per_image if r["region_correct"])

    print(f"\n── Multimodal Eval Results ({n} image(s)) ──────────────────────────────")
    print(f"  Mean Structure F1:      {mean_f1:.3f}")
    print(f"  Mean Precision:         {mean_precision:.3f}")
    print(f"  Mean Recall:            {mean_recall:.3f}")
    print(f"  Diagram Match Rate:     {match_rate:.3f}  ({n_match}/{n} correct)")
    print(f"  Region Accuracy:        {region_rate:.3f}  ({n_region}/{n} correct)")
    print(f"  Confidence distribution: {conf_dist}")
    print(f"\n  Saved → {RESULTS_PATH}")
