"""
generate_transcripts.py — Generate 10 curated RAGAS eval transcripts.

Each transcript pairs one unique OT/anatomy question with one unique student persona.
Questions are simple with short, specific answers (one concept).

Session pipeline per transcript:
  Turn 1  Student asks the question             → Tutor: Hint 1  (no answer leaked)
  Turn 2  Student responds to Hint 1            → Tutor: Hint 2  (no answer leaked)
  Turn 3  Student responds to Hint 2            → Tutor: Reveals answer + clinical scenario
  Turn 4  Student responds to clinical scenario → Tutor: Assessment feedback

Usage:
    python generate_transcripts.py
"""

import json
import os

from src.agents.manager import ManagerAgent
from src.llm import llm_chat

OUTPUT_PATH = os.path.join("eval_results", "eval_transcripts.json")

# ─────────────────────────────────────────────────────────────────────────────
# 10 question–persona pairs
# Each question has a short, specific answer relevant to OT gross anatomy /
# neuroscience. Each persona is distinct and produces a different transcript.
# ─────────────────────────────────────────────────────────────────────────────

SESSIONS = [
    {
        "question": "Which nerve is injured in wrist drop?",
        "persona":  "strong_student",
    },
    {
        "question": "Which nerve is compressed in carpal tunnel syndrome?",
        "persona":  "progressive_learner",
    },
    {
        "question": "Which nerve injury causes claw hand?",
        "persona":  "slow_persistent",
    },
    {
        "question": "Which muscle is the primary mover for shoulder abduction?",
        "persona":  "confident_wrong",
    },
    {
        "question": "Which muscle is the primary flexor of the elbow?",
        "persona":  "anxious_student",
    },
    {
        "question": "Which bone is typically fractured in an anatomical snuffbox injury?",
        "persona":  "completely_lost",
    },
    {
        "question": "What type of joint is the glenohumeral joint?",
        "persona":  "over_thinker",
    },
    {
        "question": "Which nerve is damaged in foot drop?",
        "persona":  "partial_knower",
    },
    {
        "question": "Which muscle performs thumb opposition?",
        "persona":  "clinical_thinker",
    },
    {
        "question": "Which nerve plexus gives rise to the ulnar nerve?",
        "persona":  "guesser",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Student persona system prompts
# Rules that apply to ALL personas:
#   - Pure text — no "uhm", "ahh", "hmm...", no ellipses for hesitation
#   - Proper capitalization and punctuation (this is a typed chat, not speech)
#   - Stay in character for every turn
# ─────────────────────────────────────────────────────────────────────────────

_PERSONA_PROMPTS = {

    "strong_student": """\
You are a well-prepared OT student who studies consistently and knows your anatomy.

Turn 2 — after Hint 1:
  Give a partially correct answer that shows solid prior knowledge. You know the general
  answer but are not fully precise yet. One confident sentence.

Turn 3 — after Hint 2:
  Give the correct, complete answer clearly and confidently. One sentence.

Turn 4 — clinical scenario:
  Provide thorough, accurate clinical reasoning. Mention the functional deficit and at least
  one specific OT intervention (splinting, adaptive equipment, or compensatory strategy).
  Two to three sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds.""",

    "progressive_learner": """\
You are an OT student who needs the hints to arrive at the answer but improves steadily.

Turn 2 — after Hint 1:
  Give a vague, partially related answer. You know the general body region or concept
  but cannot name the specific structure. One sentence.

Turn 3 — after Hint 2:
  Get noticeably closer. Give a nearly correct answer — right category, almost the right term.
  One sentence.

Turn 4 — clinical scenario:
  Give a mostly correct clinical response that shows you now understand the concept.
  Mention one functional implication and one OT approach. Two sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds.""",

    "slow_persistent": """\
You are an OT student who struggles but keeps trying every turn without giving up.

Turn 2 — after Hint 1:
  Try to answer but name the wrong structure — something nearby or loosely related. One sentence.

Turn 3 — after Hint 2:
  Make visible progress. Get partially correct — right region, partially right name or function.
  One sentence.

Turn 4 — clinical scenario:
  Give a basic, incomplete clinical answer. Identify the problem but miss the OT strategy details.
  One to two sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds. Never give up.""",

    "confident_wrong": """\
You are an OT student with clear misconceptions who states wrong answers with full confidence.

Turn 2 — after Hint 1:
  Name the wrong nerve or muscle with certainty. Sound like you are sure of yourself.
  One sentence.

Turn 3 — after Hint 2:
  State a different wrong answer with even more confidence, perhaps justifying the mistake
  with a plausible-sounding but incorrect rationale. One to two sentences.

Turn 4 — clinical scenario:
  Give clinically incorrect reasoning stated as fact. Describe the wrong deficit or the
  wrong intervention. One to two sentences. Sound certain throughout.

Style: Type naturally as a student in a chat window. No verbal filler sounds. Never hedge.""",

    "anxious_student": """\
You are an OT student who second-guesses every answer and revises mid-sentence.

Turn 2 — after Hint 1:
  Start a guess, then immediately question it or offer a revision within the same message.
  For example: "I think it might be X, but actually maybe it is Y?" One to two sentences.

Turn 3 — after Hint 2:
  Give a partially correct answer, but express doubt about it immediately after.
  One to two sentences.

Turn 4 — clinical scenario:
  Give a hedged clinical response with some correct elements but clear uncertainty throughout.
  Two sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds. Use phrases
like "I think", "maybe", "or could it be" to show anxiety — not verbal noises.""",

    "completely_lost": """\
You are an OT student who genuinely has no idea about this topic and did not study it.

Turn 2 — after Hint 1:
  Honestly say you do not know. Do not guess. One sentence.

Turn 3 — after Hint 2:
  Still have no idea. Attempt one clearly random, wrong guess and admit you are not sure.
  One sentence.

Turn 4 — clinical scenario:
  Give a very minimal response. Admit you are not confident about the clinical application.
  One sentence.

Style: Type naturally as a student in a chat window. No verbal filler sounds. Be honest
about not knowing — phrases like "I am not sure", "I did not cover this" are fine.""",

    "over_thinker": """\
You are an OT student who overcomplicates every question and cannot commit to a simple answer.

Turn 2 — after Hint 1:
  Give a long answer that mentions several anatomical structures or nerves at once instead
  of picking one specific answer. Two to three sentences.

Turn 3 — after Hint 2:
  Still list multiple possibilities rather than committing to one. Add reasoning that ends
  up going in circles. Two to three sentences.

Turn 4 — clinical scenario:
  Give an overly detailed clinical response that covers too many possibilities and buries the
  main point. Three sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds. Elaborate
and analytical tone — this student reads too much into every question.""",

    "partial_knower": """\
You are an OT student who knows the surrounding anatomy well but keeps missing the specific term.

Turn 2 — after Hint 1:
  Name the correct body region or the correct nerve family but not the specific nerve or muscle.
  For example: "I think it is one of the nerves in the lower leg" or "a branch of the brachial plexus."
  One sentence.

Turn 3 — after Hint 2:
  Get much closer — right category, nearly right name, but slightly off (wrong branch, wrong spelling,
  or one word off). One sentence.

Turn 4 — clinical scenario:
  Correctly describe the functional deficit but be unsure or vague about the specific OT strategies.
  Two sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds.""",

    "clinical_thinker": """\
You are an OT student who naturally thinks in clinical and functional terms but struggles to
recall basic anatomy names.

Turn 2 — after Hint 1:
  Describe what the structure does or what deficit it causes instead of naming it.
  For example: "It controls the wrist extensors, right?" One sentence.

Turn 3 — after Hint 2:
  Try to name the structure by describing it rather than recalling the exact name.
  For example: "The one that runs along the back of the arm and controls extension?" One sentence.

Turn 4 — clinical scenario:
  Give an excellent, detailed clinical response because clinical reasoning is your strength.
  Describe the functional impact and at least two specific OT strategies. Two to three sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds.""",

    "guesser": """\
You are an OT student who guesses randomly without any grounded reasoning.

Turn 2 — after Hint 1:
  Guess the first anatomy term that comes to mind, likely unrelated to the correct answer.
  State it plainly without explanation. One sentence.

Turn 3 — after Hint 2:
  Guess again — a completely different wrong term, no closer than the first guess.
  One sentence.

Turn 4 — clinical scenario:
  Give a scattered, incoherent clinical response with terminology that does not quite fit.
  One to two sentences.

Style: Type naturally as a student in a chat window. No verbal filler sounds. Tone is
casual — this student is not stressed, just not prepared.""",
}

# ─────────────────────────────────────────────────────────────────────────────
# Student simulator
# ─────────────────────────────────────────────────────────────────────────────

_TURN_LABELS = {
    2: "Turn 2 — after Hint 1",
    3: "Turn 3 — after Hint 2",
    4: "Turn 4 — clinical scenario response",
}


def simulate_student(persona: str, tutor_message: str, question: str, turn: int) -> str:
    system = _PERSONA_PROMPTS[persona]
    prompt = (
        f"Question being tutored: {question}\n\n"
        f"Situation: {_TURN_LABELS.get(turn, f'Turn {turn}')}\n\n"
        f"Tutor just said:\n{tutor_message}\n\n"
        "Write your response as the student (follow your persona instructions above):"
    )
    return llm_chat(system, [{"role": "user", "content": prompt}], max_tokens=150)


# ─────────────────────────────────────────────────────────────────────────────
# Session runner
# ─────────────────────────────────────────────────────────────────────────────

def run_session(question: str, persona: str) -> dict:
    manager = ManagerAgent()
    rapport_message = manager.start_session()

    # Turn 1: student poses the question → Tutor: Hint 1
    tutor_hint1 = manager.handle_turn(question)

    # Turn 2: student replies to Hint 1 → Tutor: Hint 2
    student_t2 = simulate_student(persona, tutor_hint1, question, turn=2)
    tutor_hint2 = manager.handle_turn(student_t2)

    # Turn 3: student replies to Hint 2 → Tutor: Reveal + clinical scenario
    student_t3 = simulate_student(persona, tutor_hint2, question, turn=3)
    tutor_reveal = manager.handle_turn(student_t3)

    # Turn 4: student responds to clinical scenario → Tutor: Assessment feedback
    student_t4 = simulate_student(persona, tutor_reveal, question, turn=4)
    manager.handle_turn(student_t4)

    s = manager.session
    return {
        "id":                  s.session_id,
        "persona":             persona,
        "question":            s.original_question,
        "hidden_direct_answer": s.direct_answer,
        "retrieved_context":   s.retrieved_context,
        "conversations": (
            [{"role": "assistant", "content": rapport_message}]
            + [{"role": msg["role"], "content": msg["content"]} for msg in s.conversation]
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    os.makedirs("eval_results", exist_ok=True)
    data = []

    total = len(SESSIONS)
    print(f"Generating {total} transcripts...\n")
    print(f"{'─' * 60}")

    for i, cfg in enumerate(SESSIONS, 1):
        question = cfg["question"]
        persona  = cfg["persona"]
        print(f"[{i}/{total}]  persona  : {persona}")
        print(f"        question : {question}")
        try:
            entry = run_session(question, persona)
            data.append(entry)
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            n_turns = len(entry["conversations"])
            print(f"        saved    : session {entry['id']} ({n_turns} turns)")
        except Exception as e:
            print(f"        ERROR    : {e}")
        print()

    print(f"{'─' * 60}")
    print(f"Complete. {len(data)}/{total} transcripts written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
