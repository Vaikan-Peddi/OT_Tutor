from fastapi import APIRouter, Depends
from sqlalchemy import func, desc
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Session, Attempt, Mistake

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard(db: DBSession = Depends(get_db)):
    total_sessions = db.query(func.count(Session.id)).scalar() or 0

    all_attempts = db.query(Attempt).all()
    scores = [a.proximity_score for a in all_attempts if a.proximity_score is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    mastery_done = (
        db.query(func.count(Session.id)).filter(Session.mastery_done == True).scalar() or 0
    )

    # Weak spots: topics with wrong/partial answers, ranked by frequency
    mistakes = db.query(Mistake).all()
    topic_counts: dict[str, int] = {}
    for m in mistakes:
        topic = m.topic or "Unknown"
        topic_counts[topic] = topic_counts.get(topic, 0) + 1

    weak_spots = [
        {"topic": k, "count": v}
        for k, v in sorted(topic_counts.items(), key=lambda x: -x[1])
    ]

    # Answer quality breakdown
    quality_counts: dict[str, int] = {"correct": 0, "partial": 0, "wrong": 0, "unanswered": 0}
    for a in all_attempts:
        q = a.answer_quality or "unanswered"
        quality_counts[q] = quality_counts.get(q, 0) + 1

    # Recent sessions
    recent = db.query(Session).order_by(desc(Session.started_at)).limit(10).all()
    recent_sessions = [
        {
            "id": s.id,
            "question": s.question,
            "topic_label": s.topic_label,
            "phase": s.phase,
            "turn_count": s.turn_count,
            "avg_score": s.avg_score,
            "mastery_done": s.mastery_done,
            "started_at": s.started_at,
        }
        for s in recent
    ]

    return {
        "total_sessions": total_sessions,
        "avg_score": avg_score,
        "mastery_completed": mastery_done,
        "weak_spots": weak_spots,
        "quality_breakdown": quality_counts,
        "recent_sessions": recent_sessions,
    }
