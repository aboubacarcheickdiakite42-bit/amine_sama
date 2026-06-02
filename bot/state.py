"""
Gestion de l'état persistant du bot.
Garde en mémoire les animes déjà publiés pour éviter les doublons.
"""

import json
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "published_animes.json")
MAX_AGE_DAYS = 30  # Oublier les animes publiés après 30 jours


def load_state() -> dict:
    """Charge l'état depuis le fichier JSON."""
    if not os.path.exists(STATE_FILE):
        return {"published": {}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Impossible de charger l'état: {e}")
        return {"published": {}}


def save_state(state: dict) -> None:
    """Sauvegarde l'état dans le fichier JSON."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Impossible de sauvegarder l'état: {e}")


def is_already_published(title: str) -> bool:
    """Vérifie si un anime a déjà été publié récemment."""
    state = load_state()
    key = title.lower().strip()
    published = state.get("published", {})

    if key not in published:
        return False

    # Vérifier si l'entrée est encore récente
    try:
        published_at = datetime.fromisoformat(published[key])
        if datetime.now() - published_at > timedelta(days=MAX_AGE_DAYS):
            # Trop vieux, on peut republier
            return False
    except Exception:
        pass

    return True


def mark_as_published(title: str) -> None:
    """Marque un anime comme publié."""
    state = load_state()
    key = title.lower().strip()
    if "published" not in state:
        state["published"] = {}
    state["published"][key] = datetime.now().isoformat()
    save_state(state)
    logger.debug(f"Marqué comme publié: {title}")


def cleanup_old_entries() -> int:
    """Supprime les entrées trop vieilles. Retourne le nombre supprimé."""
    state = load_state()
    published = state.get("published", {})
    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    to_delete = []

    for key, ts in published.items():
        try:
            if datetime.fromisoformat(ts) < cutoff:
                to_delete.append(key)
        except Exception:
            to_delete.append(key)

    for key in to_delete:
        del published[key]

    if to_delete:
        state["published"] = published
        save_state(state)
        logger.info(f"Nettoyé {len(to_delete)} anciennes entrées")

    return len(to_delete)


def get_published_count() -> int:
    """Retourne le nombre d'animes publiés en mémoire."""
    state = load_state()
    return len(state.get("published", {}))
