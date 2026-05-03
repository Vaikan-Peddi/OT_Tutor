"""
agents/manager.py — QuestionSession dataclass + ManagerAgent orchestration logic.

PIPELINE (per question):
  Turn 1 → RAG fetch + Initializer runs → Tutor gives Hint 1 (NO answer, no spoilers)
  Turn 2 → Tutor gives Hint 2 (still NO answer)
  Turn 3 → Tutor REVEALS the direct answer fully, then presents clinical scenario
  Turn 4+ → Assessment phase: student reasons through clinical scenario
  /mastery → Full mastery summary (replaces /reveal)

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

    Phases:
      "tutoring"   → turns 1-2: Socratic hints, answer masked
      "reveal"     → turn 3: tutor gives full answer + clinical scenario
      "assessment" → turn 4+: student reasons through clinical scenario
      "mastery"    → after /mastery command: full summary
    """

    session_id        : str  = field(default_factory=lambda: str(uuid.uuid4())[:8])
    original_question : str  = ""
    started_at        : str  = field(default_factory=lambda: datetime.datetime.now().isoformat())

    # ── Phase tracking ────────────────────────────────────────────────────
    turn_count : int = 0
    phase      : str = "tutoring"   # "tutoring" | "reveal" | "assessment" | "mastery"

    # ── Mastery command gating ─────────────────────────────────────────────
    mastery_unlocked : bool = False
    mastery_done     : bool = False

    # ── Stable knowledge — set once by Initializer, never regenerated ─────
    direct_answer     : str  = ""
    useful_info       : str  = ""
    clinical_scenario : str  = ""
    related_questions : list = field(default_factory=list)

    # ── Image / multimodal session ─────────────────────────────────────────
    image_mode          : bool = False
    image_mime_type     : str  = ""
    image_identified_as : str  = ""   # e.g. "Brachial Plexus Diagram"
    image_source        : str  = ""   # "stored" | "vlm"

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
        # Record a weak spot for every non-correct attempt
        if quality in ("wrong", "partial", "unanswered"):
            raw_msg = student_msg.strip()
            excerpt = (
                mistake_excerpt
                or summary
                or (f'"{raw_msg[:120]}"' if raw_msg else "no response given")
            )
            self.mistakes.append({
                "topic"  : self.topic_label or "unknown",
                "excerpt": excerpt[:200],
            })

    def to_db_record(self) -> dict:
        return {
            "session_id"          : self.session_id,
            "original_question"   : self.original_question,
            "started_at"          : self.started_at,
            "topic_label"         : self.topic_label,
            "turn_count"          : self.turn_count,
            "final_phase"         : self.phase,
            "attempts"            : self.attempts,
            "mistakes"            : self.mistakes,
            "direct_answer"       : self.direct_answer,
            "image_mode"          : self.image_mode,
            "image_identified_as" : self.image_identified_as,
            "image_source"        : self.image_source,
        }


# ─────────────────────────────────────────────────────────────────────────────
# ManagerAgent
# ─────────────────────────────────────────────────────────────────────────────

class ManagerAgent:
    """
    Orchestrates the full tutoring conversation.

    Call start_session() once when the student connects — fires rapport greeting.
    Then call handle_turn() for every student message.
    """

    def __init__(self):
        self.session            : Optional[QuestionSession] = None
        self.global_history     : list = []
        self.weak_topics        : list = []
        self._awaiting_question : bool = False

    # ── Called once at conversation start ─────────────────────────────────

    def start_session(self) -> str:
        from src.agents.rapport import run_rapport
        self._awaiting_question = True
        return run_rapport(weak_topics=self.weak_topics)

    # ── Called for every student message ──────────────────────────────────

    def handle_turn(
        self,
        student_message: str,
        image_bytes: bytes | None = None,
        mime_type: str = "image/png",
    ) -> str:
        """
        Process one student message (and optional image) and return the agent's reply.

        Args:
            student_message: raw text from the student (may be empty if image-only).
            image_bytes:     raw image bytes on the FIRST turn of an image session.
                             Pass None on all subsequent turns — the session already
                             knows it is in image_mode.
            mime_type:       MIME type of the uploaded image (default "image/png").
        """
        from src.agents.tutor   import run_tutor
        from src.agents.mastery import run_mastery

        # ── /mastery command (also catches legacy /reveal) ─────────────────
        if student_message.strip().lower() in ("/mastery", "/reveal"):
            return self._handle_mastery(run_mastery)

        has_image = image_bytes is not None

        # ── Awaiting first question after rapport ─────────────────────────
        if self._awaiting_question:
            self._awaiting_question = False
            self.session = self._open_session(
                student_message, has_image=has_image, mime_type=mime_type
            )

        # ── New question mid-conversation ─────────────────────────────────
        elif self._is_new_question(student_message):
            self.session = self._open_session(
                student_message, has_image=has_image, mime_type=mime_type
            )

        # ── Edge case: handle_turn called before start_session ────────────
        elif self.session is None:
            self.session = self._open_session(
                student_message, has_image=has_image, mime_type=mime_type
            )

        session = self.session
        session.turn_count += 1

        # Mastery command unlocks once assessment phase starts (turn 4+)
        if session.turn_count >= REVEAL_TURN_THRESHOLD:
            session.mastery_unlocked = True

        # ── First turn: initialise knowledge (image or text RAG path) ────────
        if not session.retrieved_context:
            if session.image_mode and image_bytes is not None:
                # ── Vision path ──────────────────────────────────────────────
                from src.agents.vision import run_vision_initializer
                init = run_vision_initializer(
                    image_bytes   = image_bytes,
                    mime_type     = session.image_mime_type or mime_type,
                    text_question = session.original_question,
                )
                # Store a compact sentinel so retrieved_context is truthy
                session.retrieved_context  = (
                    f"[image:{init.get('image_identified_as', 'diagram')} "
                    f"source:{init.get('image_source', 'vlm')}]"
                )
                session.retrieved_sources  = init.get("image_rag_sources", [])
                session.image_identified_as = init.get("image_identified_as", "")
                session.image_source        = init.get("image_source", "vlm")
            else:
                # ── Text RAG path (unchanged) ────────────────────────────────
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

        # ── Phase transitions ─────────────────────────────────────────────
        # Turn 1-2:  tutoring  → Socratic hints, answer strictly masked
        # Turn 3:    reveal    → give the full answer + present clinical scenario
        # Turn 4+:   assessment → student reasons through the clinical scenario
        if session.turn_count == 3 and session.phase == "tutoring":
            session.phase = "reveal"
        elif session.turn_count > 3 and session.phase in ("tutoring", "reveal"):
            session.phase = "assessment"

        # ── Per-turn analysis ─────────────────────────────────────────────
        # On the reveal turn the student hasn't answered yet, so skip evaluation.
        if session.phase in ("tutoring", "assessment"):
            analysis = run_analyzer(
                student_message      = student_message,
                original_question    = session.original_question,
                direct_answer        = session.direct_answer,
                conversation_history = session.conversation,
            )
        else:
            analysis = {
                "student_answer_quality": "unanswered",
                "proximity_score"       : 0,
                "attempt_summary"       : None,
                "mistake_excerpt"       : None,
            }

        # Attach session knowledge for the Tutor
        analysis["related_questions"]   = session.related_questions
        analysis["clinical_scenario"]   = session.clinical_scenario
        analysis["direct_answer"]       = session.direct_answer
        analysis["mastery_unlocked"]    = session.mastery_unlocked

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

        if (analysis.get("student_answer_quality") in ("wrong", "partial")
                or analysis.get("mistake_excerpt")):
            topic = session.topic_label
            if topic and topic not in self.weak_topics:
                self.weak_topics.append(topic)

        return reply

    # ── Helpers ───────────────────────────────────────────────────────────

    def _open_session(
        self,
        question: str,
        has_image: bool = False,
        mime_type: str = "",
    ) -> QuestionSession:
        if self.session:
            self.global_history.append(self.session.to_db_record())
        session = QuestionSession(original_question=question)
        if has_image:
            session.image_mode      = True
            session.image_mime_type = mime_type or "image/png"
        return session

    def _is_new_question(self, message: str) -> bool:
        if self.session is None:
            return True
        if self.session.turn_count < 2:
            return False
        # Once past tutoring phase the student is mid-scenario — never auto-switch topics.
        # Only /new (handled upstream) can start a fresh session at that point.
        if self.session.phase != "tutoring":
            return False
        if len(message.strip()) > 120:
            return False
        followup_starters = {
            "but", "and", "so", "also", "what about", "why", "how", "ok", "okay",
            "it", "is", "are", "will", "would", "could", "should", "does", "do",
            "can", "that", "this", "then", "if", "when",
        }
        lowered = message.lower().strip()
        starts_followup = any(lowered.startswith(w) for w in followup_starters)
        return message.strip().endswith("?") and not starts_followup

    def _handle_mastery(self, run_mastery) -> str:
        if self.session is None:
            return "Ask a question first before using /mastery."
        if not self.session.mastery_unlocked:
            remaining = REVEAL_TURN_THRESHOLD - self.session.turn_count
            return (
                f"You need {remaining} more turn(s) before the mastery summary unlocks. "
                "Keep working through it — you're almost there!"
            )
        self.session.phase        = "mastery"
        self.session.mastery_done = True
        return run_mastery(session=self.session)
