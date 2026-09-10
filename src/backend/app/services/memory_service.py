import os
import json
import uuid
from typing import List, Dict, Any
from app.config import settings

class MemoryService:
    def __init__(self):
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if os.path.isabs(settings.checkpoint_dir):
            self.checkpoint_dir = settings.checkpoint_dir
        else:
            self.checkpoint_dir = os.path.join(backend_root, settings.checkpoint_dir)
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def _get_filepath(self, session_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{session_id}.json")

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self._save_session(session_id, [])
        return session_id

    def _save_session(self, session_id: str, turns: List[Dict[str, Any]]):
        filepath = self._get_filepath(session_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(turns, f, indent=2, default=str)

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        filepath = self._get_filepath(session_id)
        if not os.path.exists(filepath):
            return []
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []

    def append_turn(self, session_id: str, turn: Dict[str, Any]):
        history = self.get_history(session_id)
        # Add turn index
        turn["turn_index"] = len(history) + 1
        history.append(turn)
        self._save_session(session_id, history)
        return turn["turn_index"]

    def clear(self, session_id: str) -> bool:
        filepath = self._get_filepath(session_id)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def _get_facts_filepath(self, session_id: str) -> str:
        return os.path.join(self.checkpoint_dir, f"{session_id}_facts.json")

    def save_known_facts(self, session_id: str, known_facts: Dict[str, Any]):
        """Persists accumulated known_facts for a session across fresh turns."""
        filepath = self._get_facts_filepath(session_id)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(known_facts, f, indent=2, default=str)

    def get_known_facts(self, session_id: str) -> Dict[str, Any]:
        """Loads persisted known_facts for a session. Returns empty dict if none."""
        filepath = self._get_facts_filepath(session_id)
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

memory_service = MemoryService()
