"""
main.py — interactive Socratic OT tutoring session.

Usage:
    python main.py

Commands during chat:
    /reveal   — show the direct answer (unlocks after 3 turns)
    /quit     — exit
    /new      — force-start a new question session
    /status   — print session summary
"""

from src.agents.manager import ManagerAgent


def main():
    print("=" * 60)
    print("  OT Socratic Tutor")
    print("  Type your anatomy/OT question to begin.")
    print("  Commands: /reveal  /new  /status  /quit")
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
            break

        if user_input.lower() == "/new":
            manager.session = None
            print("[New session started — ask your question.]")
            continue

        if user_input.lower() == "/status" and manager.session:
            s = manager.session
            print(f"\n[Session {s.session_id} | Turn {s.turn_count} | Phase: {s.phase}]")
            print(f"  Topic: {s.topic_label or 'TBD'}")
            print(f"  Attempts: {len(s.attempts)}")
            print(f"  Mistakes: {len(s.mistakes)}")
            continue

        reply = manager.handle_turn(user_input)
        print(f"\nTutor: {reply}")


if __name__ == "__main__":
    main()
