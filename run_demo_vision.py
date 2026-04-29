"""
run_demo_vision.py — CLI demo for Task 4: Multimodal Diagram Tutoring.

Usage:
    python run_demo_vision.py --image data/images/brachial_plexus.png
    python run_demo_vision.py --image hand.jpg --question "What nerve innervates the thenar muscles?"

Requires:
    - GEMINI_API_KEY in .env
    - One of GROQ_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY in .env (for the Socratic tutor)
    - pip install -r requirements.txt
"""

import argparse
import sys
from pathlib import Path


MIME_MAP = {
    ".jpg" : "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png" : "image/png",
    ".gif" : "image/gif",
    ".webp": "image/webp",
    ".bmp" : "image/bmp",
}

BANNER = "=" * 62


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OT Tutor — Multimodal Diagram Demo (Task 4)"
    )
    parser.add_argument(
        "--image", required=True,
        help="Path to an anatomical diagram image (PNG/JPG/WEBP)."
    )
    parser.add_argument(
        "--question", default="",
        help="Optional text question about the image."
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[error] Image not found: {image_path}")
        sys.exit(1)

    suffix    = image_path.suffix.lower()
    mime_type = MIME_MAP.get(suffix, "image/png")
    image_bytes = image_path.read_bytes()

    from src.agents.manager import ManagerAgent
    manager = ManagerAgent()

    print(BANNER)
    print("  OT Tutor — Multimodal Diagram Tutoring Session")
    print(BANNER)
    print(f"  Image : {image_path.name}")
    print(f"  MIME  : {mime_type}")
    print(BANNER)

    # ── Rapport greeting ───────────────────────────────────────────────────
    greeting = manager.start_session()
    print(f"\nTutor: {greeting}\n")

    # ── Turn 1: image + optional question ─────────────────────────────────
    first_message = args.question or f"I uploaded a diagram — {image_path.stem.replace('_', ' ')}. What is this image?"
    print(f"You  : {first_message}  [+ image: {image_path.name}]")

    response = manager.handle_turn(
        student_message = first_message,
        image_bytes     = image_bytes,
        mime_type       = mime_type,
    )
    print(f"\nTutor: {response}\n")

    # ── Show what was identified ───────────────────────────────────────────
    session = manager.session
    if session and session.image_mode:
        src_label = "stored diagram (ground truth)" if session.image_source == "stored" else "Gemini Vision (VLM)"
        print(f"  [vision] Identified as : {session.image_identified_as}")
        print(f"  [vision] Context source: {src_label}")
        print(f"  [vision] Topic label   : {session.topic_label}")
        print()

    # ── Interactive conversation loop ──────────────────────────────────────
    print("  Commands: /mastery   → full mastery summary")
    print("            /quit      → end session")
    print(BANNER)

    while True:
        try:
            user_input = input("You  : ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Session ended]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("[Session ended]")
            break

        # Subsequent turns have no image bytes — the session is already in image_mode
        response = manager.handle_turn(user_input)
        print(f"\nTutor: {response}\n")


if __name__ == "__main__":
    main()
