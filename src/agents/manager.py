"""
agents/manager.py — QuestionSession dataclass + ManagerAgent orchestration logic.

Conversation lifecycle:
  1. Manager.start_session() called at connect time → RapportAgent fires proactively
  2. Student sends their question → Initializer runs (RAG + stable knowledge)
  3. Tutoring loop (turns 1-2: direct_answer masked; turn 3+: unmasked)
  4. Assessment phase (turn_count > 4, clinical scenario presented)
  5. /reveal → RevealAgent generates full mastery summary

The Manager is the only agent with full state visibility.
"""

import uuid
import datetime
from dataclasses import dataclass, field
from typing import Optional

from src.config import REVEAL_TURN_THRESHOLD
from src.retriever import retrieve_context
from src.agents.analyzer import run_initializer, run_analyzer


# ─────────────────────────────────────────────────────────────────────────────
# QuestionSession
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class QuestionSession:
    """
    Isolated context for one student question.
    Phases: tutoring → assessment → revealed
    (Rapport happens at ManagerAgent level before any session opens.)
    """

    session_id        : str  = field(default_factory=lambda: str(uuid.uuid4())[:8])
    original_question : str  = ""
    started_at        : str  = field(default_factory=lambda: datetime.datetime.now().isoformat())

    # ── Phase tracking ────────────────────────────────────────────────────
    turn_count : int = 0
    # Valid values: "tutoring" | "assessment" | "revealed"
    phase      : str = "tutoring"

    # ── Reveal gating ─────────────────────────────────────────────────────
    reveal_unlocked : bool = False
    reveal_offered  : bool = False
    revealed        : bool = False

    # ── Stable knowledge — set once by Initializer, never regenerated ─────
    direct_answer     : str  = ""
    useful_info       : str  = ""
    clinical_scenario : str  = ""
    related_questions : list = field(default_factory=list)

    # ── Conversation history (LLM format) ─────────────────────────────────
    conversation : list = field(default_factory=list)

    # ── Structured logs ───────────────────────────────────────────────────
    topic_label    : str  = ""
    attempts       : list = field(default_factory=list)
    mistakes       : list = field(default_factory=list)
    revisit_topics : list = field(default_factory=list)

    # ── RAG cache ─────────────────────────────────────────────────────────
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
    Orchestrates the full tutoring conversation.

    Call start_session() once when the student connects — this fires the rapport
    greeting proactively. Then call handle_turn() for every student message.
    """

    def __init__(self):
        self.session            : Optional[QuestionSession] = None
        self.global_history     : list = []
        self.weak_topics        : list = []
        # True after rapport has fired, waiting for student's actual question.
        self._awaiting_question : bool = False

    # ── Called once at conversation start ─────────────────────────────────

    def start_session(self) -> str:
        """
        Send the rapport greeting proactively, before any student message.
        Call this once when the student connects / the chat UI opens.

        Returns:
            The rapport greeting string to display to the student.
        """
        from src.agents.rapport import run_rapport
        self._awaiting_question = True
        return run_rapport(weak_topics=self.weak_topics)

    # ── Called for every student message ──────────────────────────────────

    def handle_turn(self, student_message: str) -> str:
        """Process one student message and return the agent's reply."""
        from src.agents.tutor  import run_tutor
        from src.agents.reveal import run_reveal

        # ── /reveal command ───────────────────────────────────────────────
        if student_message.strip().lower() == "/reveal":
            return self._handle_reveal(run_reveal)

        # ── Awaiting first question after rapport ─────────────────────────
        # The student's first message IS their anatomy question — open a session.
        if self._awaiting_question:
            self._awaiting_question = False
            self.session = self._open_session(student_message)

        # ── New question mid-conversation ─────────────────────────────────
        elif self._is_new_question(student_message):
            self.session = self._open_session(student_message)

        # ── Edge case: handle_turn called before start_session ────────────
        elif self.session is None:
            self.session = self._open_session(student_message)

        session = self.session
        session.turn_count += 1

        if session.turn_count >= REVEAL_TURN_THRESHOLD:
            session.reveal_unlocked = True

        # ── First turn: RAG retrieval + Initializer ───────────────────────
        if not session.retrieved_context:
            ctx, srcs = retrieve_context(session.original_question)
            session.retrieved_context = ctx
            session.retrieved_sources = srcs

            init = run_initializer(
                original_question = session.original_question,
                context           = session.retrieved_context,
            )
            session.direct_answer     = init["direct_answer"]
            session.clinical_scenario = init["clinical_scenario"]
            session.related_questions = init["related_questions"]
            session.useful_info       = init["useful_info"]
            session.topic_label       = init["topic_label"]

        # ── Every turn: evaluate student response ─────────────────────────
        analysis = run_analyzer(
            student_message      = student_message,
            original_question    = session.original_question,
            direct_answer        = session.direct_answer,
            conversation_history = session.conversation,
        )

        # Attach stable questions so Tutor can pick one
        analysis["related_questions"] = session.related_questions

        # Masking: Tutor only sees direct_answer after the first 2 turns
        analysis["direct_answer_for_tutor"] = (
            session.direct_answer if session.turn_count > 2 else None
        )

        # Phase transition: tutoring → assessment after turn 4
        if session.turn_count > 4 and session.phase == "tutoring":
            session.phase = "assessment"

        reply = run_tutor(
            student_message = student_message,
            analysis        = analysis,
            session         = session,
        )

        session.conversation.append({"role": "user",      "content": student_message})
        session.conversation.append({"role": "assistant", "content": reply})

        session.log_attempt(
            turn            = session.turn_count,
            student_msg     = student_message,
            tutor_msg       = reply,
            quality         = analysis.get("student_answer_quality", "unanswered"),
            score           = analysis.get("proximity_score", 0),
            summary         = analysis.get("attempt_summary"),
            mistake_excerpt = analysis.get("mistake_excerpt"),
        )

        if analysis.get("student_answer_quality") in ("wrong", "partial"):
            topic = session.topic_label
            if topic and topic not in self.weak_topics:
                self.weak_topics.append(topic)

        return reply

    # ── Helpers ───────────────────────────────────────────────────────────

    def _open_session(self, question: str) -> QuestionSession:
        if self.session:
            self.global_history.append(self.session.to_db_record())
        return QuestionSession(original_question=question)

    def _is_new_question(self, message: str) -> bool:
        if self.session is None:
            return True
        if self.session.turn_count < 2:
            return False
        followup_starters = {"but", "and", "so", "also", "what about", "why", "how", "ok", "okay"}
        lowered = message.lower().strip()
        starts_followup = any(lowered.startswith(w) for w in followup_starters)
        return message.strip().endswith("?") and not starts_followup

    def _handle_reveal(self, run_reveal) -> str:
        if self.session is None:
            return "Ask a question first before using /reveal."
        if not self.session.reveal_unlocked:
            remaining = REVEAL_TURN_THRESHOLD - self.session.turn_count
            return (
                f"You need {remaining} more attempt(s) before revealing the answer. "
                "Keep going — you're getting there!"
            )
        self.session.phase    = "revealed"
        self.session.revealed = True
        return run_reveal(session=self.session)
