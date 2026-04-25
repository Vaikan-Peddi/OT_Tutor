"""
agents/manager.py — QuestionSession dataclass + ManagerAgent orchestration logic.
"""

import uuid
import datetime
from dataclasses import dataclass, field
from typing import Optional

from src.config import REVEAL_TURN_THRESHOLD
from src.retriever import retrieve_context
from src.agents.analyzer import run_analyzer


# ─────────────────────────────────────────────────────────────────────────────
# QuestionSession
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QuestionSession:
    """Isolated context per student question. Serialisable via to_db_record()."""

    session_id       : str  = field(default_factory=lambda: str(uuid.uuid4())[:8])
    original_question: str  = ""
    started_at       : str  = field(default_factory=lambda: datetime.datetime.now().isoformat())

    turn_count      : int  = 0
    phase           : str  = "tutoring"    # "tutoring" | "assessment" | "revealed"

    reveal_unlocked : bool = False
    reveal_offered  : bool = False
    revealed        : bool = False

    direct_answer     : str = ""
    useful_info       : str = ""
    clinical_scenario : str = ""

    conversation: list = field(default_factory=list)

    topic_label    : str  = ""
    attempts       : list = field(default_factory=list)
    mistakes       : list = field(default_factory=list)
    revisit_topics : list = field(default_factory=list)

    retrieved_context : str  = ""
    retrieved_sources : list = field(default_factory=list)

    def log_attempt(
        self,
        turn: int,
        student_msg: str,
        tutor_msg: str,
        quality: str,
        score: int,
        summary: Optional[str],
        mistake_excerpt: Optional[str],
    ):
        self.attempts.append({
            "turn"           : turn,
            "phase"          : self.phase,
            "student_message": student_msg,
            "tutor_response" : tutor_msg,
            "answer_quality" : quality,
            "proximity_score": score,
            "attempt_summary": summary,
        })
        if mistake_excerpt:
            self.mistakes.append({
                "topic"  : self.topic_label or "unknown",
                "excerpt": mistake_excerpt,
            })

    def to_db_record(self) -> dict:
        return {
            "session_id"       : self.session_id,
            "original_question": self.original_question,
            "started_at"       : self.started_at,
            "topic_label"      : self.topic_label,
            "turn_count"       : self.turn_count,
            "final_phase"      : self.phase,
            "attempts"         : self.attempts,
            "mistakes"         : self.mistakes,
            "direct_answer"    : self.direct_answer,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ManagerAgent
# ─────────────────────────────────────────────────────────────────────────────

class ManagerAgent:
    """
    Orchestrates one conversation: session bookkeeping, RAG retrieval,
    Analyzer calls, phase transitions, and /reveal gating.

    Usage:
        manager = ManagerAgent()
        reply   = manager.handle_turn(student_message)
    """

    def __init__(self):
        self.session: Optional[QuestionSession] = None
        self.global_history: list = []          # full multi-session history
        self.weak_topics: list    = []           # cross-session struggle topics

    # ── Public entry point ─────────────────────────────────────────────────

    def handle_turn(self, student_message: str) -> str:
        """Process one student message; return the tutor's reply."""
        from src.agents.tutor import run_tutor   # local import to avoid circular

        # ── /reveal command ────────────────────────────────────────────────
        if student_message.strip().lower() == "/reveal":
            return self._handle_reveal()

        # ── New session detection ──────────────────────────────────────────
        if self.session is None or self._is_new_question(student_message):
            self.session = self._open_session(student_message)

        session = self.session
        session.turn_count += 1

        # ── Unlock /reveal after threshold ────────────────────────────────
        if session.turn_count >= REVEAL_TURN_THRESHOLD:
            session.reveal_unlocked = True

        # ── RAG retrieval (only on turn 1 of each session) ────────────────
        if session.turn_count == 1:
            ctx, srcs = retrieve_context(session.original_question)
            session.retrieved_context = ctx
            session.retrieved_sources = srcs

        # ── Analyzer ──────────────────────────────────────────────────────
        analysis = run_analyzer(
            student_message          = student_message,
            context                  = session.retrieved_context,
            question_session_history = session.conversation,
            original_question        = session.original_question,
        )

        # Persist private knowledge on first turn
        if session.turn_count == 1:
            session.direct_answer     = analysis.get("direct_answer", "")
            session.useful_info       = analysis.get("useful_info", "")
            session.clinical_scenario = analysis.get("clinical_scenario", "")
            session.topic_label       = analysis.get("topic_label") or ""

        # Phase transition to assessment after turn 3
        if session.turn_count > 3 and session.phase == "tutoring":
            session.phase = "assessment"

        # ── Tutor ─────────────────────────────────────────────────────────
        tutor_reply = run_tutor(
            student_message  = student_message,
            analysis         = analysis,
            session          = session,
        )

        # ── Update conversation history ────────────────────────────────────
        session.conversation.append({"role": "user",      "content": student_message})
        session.conversation.append({"role": "assistant", "content": tutor_reply})

        # Log attempt
        session.log_attempt(
            turn            = session.turn_count,
            student_msg     = student_message,
            tutor_msg       = tutor_reply,
            quality         = analysis.get("student_answer_quality", "unanswered"),
            score           = analysis.get("proximity_score", 0),
            summary         = analysis.get("attempt_summary"),
            mistake_excerpt = analysis.get("mistake_excerpt"),
        )

        # Track weak topics globally
        if analysis.get("student_answer_quality") in ("wrong", "partial"):
            topic = session.topic_label
            if topic and topic not in self.weak_topics:
                self.weak_topics.append(topic)

        return tutor_reply

    # ── Helpers ────────────────────────────────────────────────────────────

    def _open_session(self, question: str) -> QuestionSession:
        if self.session:
            self.global_history.append(self.session.to_db_record())
        return QuestionSession(original_question=question)

    def _is_new_question(self, message: str) -> bool:
        """Heuristic: treat message as new question if session has ≥3 turns
        and message ends with '?' and doesn't look like a follow-up."""
        if self.session is None:
            return True
        if self.session.turn_count < 2:
            return False
        followup_words = {"but", "and", "so", "also", "what about", "why", "how", "ok", "okay"}
        lowered = message.lower().strip()
        starts_followup = any(lowered.startswith(w) for w in followup_words)
        return message.strip().endswith("?") and not starts_followup

    def _handle_reveal(self) -> str:
        if self.session is None:
            return "Ask a question first before using /reveal."
        if not self.session.reveal_unlocked:
            return (
                f"You need at least {REVEAL_TURN_THRESHOLD} attempts before revealing the answer. "
                f"Keep trying — you're on turn {self.session.turn_count}!"
            )
        self.session.phase    = "revealed"
        self.session.revealed = True
        return (
            f"**Direct answer:**\n{self.session.direct_answer}\n\n"
            f"**Useful clinical note:**\n{self.session.useful_info}"
        )
