from sqlalchemy import Column, String, Integer, Boolean, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    question = Column(Text, nullable=True)
    started_at = Column(String)
    phase = Column(String, default="tutoring")
    turn_count = Column(Integer, default=0)
    mastery_unlocked = Column(Boolean, default=False)
    mastery_done = Column(Boolean, default=False)
    topic_label = Column(String, nullable=True)
    image_mode = Column(Boolean, default=False)
    image_identified_as = Column(String, nullable=True)
    mastery_text = Column(Text, nullable=True)
    avg_score = Column(Float, nullable=True)

    messages = relationship(
        "Message", back_populates="session",
        cascade="all, delete-orphan", order_by="Message.id",
    )
    attempts = relationship("Attempt", back_populates="session", cascade="all, delete-orphan")
    mistakes = relationship("Mistake", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"))
    role = Column(String)
    content = Column(Text)
    timestamp = Column(String)
    is_mastery = Column(Boolean, default=False)

    session = relationship("Session", back_populates="messages")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"))
    turn = Column(Integer)
    phase = Column(String)
    student_message = Column(Text)
    tutor_response = Column(Text)
    answer_quality = Column(String)
    proximity_score = Column(Integer, nullable=True)
    attempt_summary = Column(Text, nullable=True)

    session = relationship("Session", back_populates="attempts")


class Mistake(Base):
    __tablename__ = "mistakes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"))
    topic = Column(String)
    excerpt = Column(Text)
    correct_answer = Column(Text, nullable=True)
    original_question = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)

    session = relationship("Session", back_populates="mistakes")
