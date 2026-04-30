"""
In-memory store for active ManagerAgent instances.
One agent per web session, keyed by session_id.
Sessions are kept alive until the server restarts or they are explicitly removed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.manager import ManagerAgent

_store: dict[str, ManagerAgent] = {}


def create_agent(session_id: str) -> ManagerAgent:
    agent = ManagerAgent()
    _store[session_id] = agent
    return agent


def get_agent(session_id: str) -> Optional[ManagerAgent]:
    return _store.get(session_id)


def remove_agent(session_id: str) -> None:
    _store.pop(session_id, None)
