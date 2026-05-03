import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Mistake
from src.llm import llm_chat

router = APIRouter(tags=["mistakes"])
logger = logging.getLogger(__name__)


class QuizRequest(BaseModel):
    mistake_ids: List[int]


_QUIZ_SYSTEM = """\
You are a quiz generator for an Occupational Therapy tutoring system.
Given a set of student mistakes and the correct answers, generate exactly 4 multiple-choice \
questions that target the specific misconceptions shown. Remember to keep the 4 questions answering different parts and not the same question. We do not want the quiz questions answering the same thing in 4 different questions.

Output ONLY a JSON array of question objects — no markdown, no prose.

Schema for each question:
{
  "question": "<the question text>",
  "options": ["<A>", "<B>", "<C>", "<D>"],
  "correct_index": <0-3>,
  "explanation": "<1-2 sentence explanation of why the correct answer is right>"
}

Rules:
- Each question must directly test a concept the student got wrong.
- Wrong options (distractors) should reflect common misconceptions, including the student's \
  actual wrong answer where appropriate.
- Questions should be clinically relevant and OT-focused.
- Keep question text under 30 words.
- Keep each option under 15 words.
- Do NOT repeat the same concept twice across questions.
- Output exactly 4 question objects in the array.
"""


@router.post("/mistakes/quiz")
def generate_quiz(body: QuizRequest, db: DBSession = Depends(get_db)):
    mistakes = db.query(Mistake).filter(Mistake.id.in_(body.mistake_ids)).all()
    if not mistakes:
        raise HTTPException(status_code=404, detail="No mistakes found for given IDs.")

    # Build context block for the LLM
    mistake_lines = []
    for i, m in enumerate(mistakes, 1):
        mistake_lines.append(
            f"Mistake {i}:\n"
            f"  Topic: {m.topic or 'unknown'}\n"
            f"  Question asked: {m.original_question or 'unknown'}\n"
            f"  Student said (wrong): {m.excerpt or 'unknown'}\n"
            f"  Correct answer: {m.correct_answer or 'not available'}"
        )

    prompt = (
        "STUDENT MISTAKES TO TARGET:\n\n"
        + "\n\n".join(mistake_lines)
        + "\n\nGenerate 4 MCQ questions now."
    )

    try:
        raw = llm_chat(_QUIZ_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=2048)
    except Exception as exc:
        logger.exception("Quiz generation failed")
        raise HTTPException(status_code=500, detail=str(exc))

    # Parse JSON — strip markdown fences if present
    text = raw.strip()
    if text.startswith("```"):
        import re
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        text = m.group(1).strip() if m else text

    try:
        questions = json.loads(text)
    except Exception:
        logger.error("Quiz JSON parse failed. Raw: %s", raw[:400])
        raise HTTPException(status_code=500, detail="Failed to parse quiz questions.")

    return {"questions": questions}


@router.post("/mistakes/resolve")
def resolve_mistakes(body: QuizRequest, db: DBSession = Depends(get_db)):
    """Mark a set of mistakes as resolved (clears them from weak spots)."""
    db.query(Mistake).filter(Mistake.id.in_(body.mistake_ids)).update(
        {"resolved": True}, synchronize_session=False
    )
    db.commit()
    return {"resolved": len(body.mistake_ids)}
