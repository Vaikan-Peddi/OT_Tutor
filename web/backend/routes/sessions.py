import uuid
import datetime
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import Session, Message, Attempt, Mistake
from ..agent_store import create_agent, get_agent, remove_agent

router = APIRouter(tags=["sessions"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.now().isoformat()


def _add_message(
    db: DBSession, session_id: str, role: str, content: str, is_mastery: bool = False
) -> None:
    db.add(Message(
        session_id=session_id, role=role, content=content,
        timestamp=_now(), is_mastery=is_mastery,
    ))


def _sync_db_session(db_sess: Session, q_sess) -> None:
    db_sess.phase = q_sess.phase
    db_sess.turn_count = q_sess.turn_count
    db_sess.mastery_unlocked = q_sess.mastery_unlocked
    db_sess.mastery_done = q_sess.mastery_done
    if q_sess.topic_label:
        db_sess.topic_label = q_sess.topic_label
    db_sess.image_mode = q_sess.image_mode
    if q_sess.image_identified_as:
        db_sess.image_identified_as = q_sess.image_identified_as
    scores = [a["proximity_score"] for a in q_sess.attempts if a.get("proximity_score") is not None]
    if scores:
        db_sess.avg_score = round(sum(scores) / len(scores), 1)


def _session_to_dict(s: Session) -> dict:
    return {
        "id": s.id,
        "question": s.question,
        "started_at": s.started_at,
        "phase": s.phase,
        "turn_count": s.turn_count,
        "mastery_unlocked": s.mastery_unlocked,
        "mastery_done": s.mastery_done,
        "topic_label": s.topic_label,
        "image_mode": s.image_mode,
        "image_identified_as": s.image_identified_as,
        "mastery_text": s.mastery_text,
        "avg_score": s.avg_score,
        "message_count": len(s.messages),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/sessions")
def create_session(db: DBSession = Depends(get_db)):
    session_id = str(uuid.uuid4())[:8]
    agent = create_agent(session_id)

    try:
        greeting = agent.start_session()
    except Exception as exc:
        remove_agent(session_id)
        raise HTTPException(status_code=500, detail=str(exc))

    db_sess = Session(
        id=session_id,
        started_at=_now(),
        phase="tutoring",
        turn_count=0,
        mastery_unlocked=False,
        mastery_done=False,
        image_mode=False,
    )
    db.add(db_sess)
    _add_message(db, session_id, "assistant", greeting)
    db.commit()

    return {
        "session_id": session_id,
        "greeting": greeting,
        "phase": "tutoring",
        "turn_count": 0,
        "mastery_unlocked": False,
    }


@router.get("/sessions")
def list_sessions(db: DBSession = Depends(get_db)):
    sessions = db.query(Session).order_by(Session.started_at.desc()).all()
    return [_session_to_dict(s) for s in sessions]


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    s = db.query(Session).filter(Session.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    d = _session_to_dict(s)
    d["messages"] = [
        {
            "id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp,
            "is_mastery": m.is_mastery,
        }
        for m in s.messages
    ]
    return d


@router.post("/sessions/{session_id}/chat")
async def chat(
    session_id: str,
    message: str = Form(""),
    image: Optional[UploadFile] = File(None),
    db: DBSession = Depends(get_db),
):
    db_sess = db.query(Session).filter(Session.id == session_id).first()
    if not db_sess:
        raise HTTPException(status_code=404, detail="Session not found")

    agent = get_agent(session_id)
    if agent is None:
        raise HTTPException(status_code=410, detail="Session expired — start a new session.")

    image_bytes: Optional[bytes] = None
    mime_type = "image/png"
    if image and image.filename:
        image_bytes = await image.read()
        mime_type = image.content_type or "image/png"

    loop = asyncio.get_event_loop()
    try:
        reply = await loop.run_in_executor(
            None, lambda: agent.handle_turn(message, image_bytes, mime_type)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    q_sess = agent.session

    if db_sess.question is None and q_sess and q_sess.original_question:
        db_sess.question = q_sess.original_question

    _add_message(db, session_id, "user", message if message else "[image uploaded]")
    _add_message(db, session_id, "assistant", reply)

    if q_sess:
        _sync_db_session(db_sess, q_sess)

        if q_sess.attempts:
            last = q_sess.attempts[-1]
            db.add(Attempt(
                session_id=session_id,
                turn=last["turn"],
                phase=last["phase"],
                student_message=last["student_message"],
                tutor_response=last["tutor_response"],
                answer_quality=last["answer_quality"],
                proximity_score=last.get("proximity_score"),
                attempt_summary=last.get("attempt_summary"),
            ))

        existing_excerpts = {m.excerpt for m in db_sess.mistakes}
        for mistake in q_sess.mistakes:
            if mistake["excerpt"] not in existing_excerpts:
                db.add(Mistake(
                    session_id=session_id,
                    topic=mistake["topic"],
                    excerpt=mistake["excerpt"],
                ))
                existing_excerpts.add(mistake["excerpt"])

    db.commit()

    return {
        "reply": reply,
        "phase": q_sess.phase if q_sess else db_sess.phase,
        "turn_count": q_sess.turn_count if q_sess else db_sess.turn_count,
        "mastery_unlocked": q_sess.mastery_unlocked if q_sess else db_sess.mastery_unlocked,
        "mastery_done": q_sess.mastery_done if q_sess else db_sess.mastery_done,
        "topic_label": (q_sess.topic_label if q_sess else db_sess.topic_label),
    }


@router.post("/sessions/{session_id}/mastery")
async def mastery(session_id: str, db: DBSession = Depends(get_db)):
    db_sess = db.query(Session).filter(Session.id == session_id).first()
    if not db_sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Return cached mastery if already generated
    if db_sess.mastery_text:
        return {"mastery_text": db_sess.mastery_text}

    agent = get_agent(session_id)
    if agent is None:
        raise HTTPException(status_code=410, detail="Session expired — start a new session.")

    loop = asyncio.get_event_loop()
    try:
        reply = await loop.run_in_executor(None, lambda: agent.handle_turn("/mastery"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    q_sess = agent.session
    if q_sess:
        _sync_db_session(db_sess, q_sess)

    db_sess.mastery_text = reply
    db_sess.mastery_done = True
    _add_message(db, session_id, "assistant", reply, is_mastery=True)
    db.commit()

    return {"mastery_text": reply}


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: DBSession = Depends(get_db)):
    db_sess = db.query(Session).filter(Session.id == session_id).first()
    if not db_sess:
        raise HTTPException(status_code=404, detail="Session not found")
    remove_agent(session_id)
    db.delete(db_sess)
    db.commit()
    return {"ok": True}
