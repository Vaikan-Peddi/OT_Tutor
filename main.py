"""
main.py — interactive Socratic OT tutoring session.

Usage:
    python main.py

Pipeline per question:
    Turn 1  → Hint 1  (no answer given)
    Turn 2  → Hint 2  (no answer given)
    Turn 3  → Full answer revealed + clinical scenario presented
    Turn 4+ → Assessment: student reasons through clinical scenario

Commands during chat:
    /mastery  — full post-session mastery summary (unlocks after turn 3)
    /new      — force-start a new question session
    /status   — print current session state
    /quit     — exit
"""

from src.agents.manager import ManagerAgent


def main():
    print("=" * 60)
    print("  OT Socratic Tutor")
    print("  Type your anatomy/OT question to begin.")
    print("  Commands: /mastery  /new  /status  /quit")
    print("=" * 60)

    manager = ManagerAgent()

    # Rapport greeting fires automatically before any student input
    opening = manager.start_session()
    print(f"\nTutor: {opening}\n")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit"):
            print("Session ended. Good luck studying!")
            # Prompt to save transcript if there is a session
            if manager.session and manager.session.turn_count > 0:
                save = input("Do you want to save this conversation for RAGAS evaluation (eval_results/eval_transcripts.json)? (y/n): ").strip().lower()
                if save == "y":
                    import json, os
                    ragas_path = os.path.join("eval_results", "eval_transcripts.json")
                    s = manager.session
                    ragas_entry = {
                        "id": s.session_id,
                        "question": s.original_question,
                        "hidden_direct_answer": s.direct_answer,
                        "retrieved_context": s.retrieved_context,
                        "conversations": [
                            {"role": msg["role"], "content": msg["content"]}
                            for msg in s.conversation
                        ],
                    }
                    try:
                        with open(ragas_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception:
                        data = []
                    data.append(ragas_entry)
                    with open(ragas_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    print(f"[Transcript saved to {ragas_path}]")
            break

        if user_input.lower() == "/new":
            manager.session = None
            manager._awaiting_question = True
            print("[New session started — ask your question.]")
            continue

        if user_input.lower() == "/status":
            if manager.session:
                s = manager.session
                print(f"\n[Session {s.session_id} | Turn {s.turn_count} | Phase: {s.phase}]")
                print(f"  Topic: {s.topic_label or 'TBD'}")
                print(f"  Attempts: {len(s.attempts)}")
                print(f"  Mistakes: {len(s.mistakes)}")
                print(f"  Mastery unlocked: {s.mastery_unlocked}")
            else:
                print("[No active session yet.]")
            continue

        reply = manager.handle_turn(user_input)
        print(f"\nTutor: {reply}")


if __name__ == "__main__":
    main()
