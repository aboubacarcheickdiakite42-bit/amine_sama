"""
Suivi des messages déjà transférés pour éviter les doublons.
"""

import json
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FORWARD_STATE_FILE = os.path.join(os.path.dirname(__file__), "forwarded_messages.json")
MAX_AGE_DAYS = 60


def load_forward_state() -> dict:
    if not os.path.exists(FORWARD_STATE_FILE):
        return {"forwarded": {}}
    try:
        with open(FORWARD_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"forwarded": {}}


def save_forward_state(state: dict) -> None:
    try:
        with open(FORWARD_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Impossible de sauvegarder l'état forwarder: {e}")


def is_message_forwarded(msg_key: str) -> bool:
    state = load_forward_state()
    return msg_key in state.get("forwarded", {})


def mark_message_forwarded(msg_key: str) -> None:
    state = load_forward_state()
    if "forwarded" not in state:
        state["forwarded"] = {}
    state["forwarded"][msg_key] = datetime.now().isoformat()
    save_forward_state(state)


def get_forwarded_count() -> int:
    return len(load_forward_state().get("forwarded", {}))


def cleanup_old_forwarded() -> int:
    state = load_forward_state()
    forwarded = state.get("forwarded", {})
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    to_delete = [k for k, v in forwarded.items() if datetime.fromisoformat(v) < cutoff]
    for k in to_delete:
        del forwarded[k]
    if to_delete:
        state["forwarded"] = forwarded
        save_forward_state(state)
    return len(to_delete)


# --- Gestion de l'état pause ---

def is_paused() -> bool:
    """Retourne True si le bot est en pause."""
    state = load_forward_state()
    return state.get("paused", False)


def set_paused(paused: bool) -> None:
    """Active ou désactive la pause."""
    state = load_forward_state()
    state["paused"] = paused
    if paused:
        state["paused_at"] = datetime.now().isoformat()
    else:
        state.pop("paused_at", None)
    save_forward_state(state)


def get_paused_since() -> str | None:
    """Retourne la date de mise en pause, ou None."""
    state = load_forward_state()
    return state.get("paused_at")
