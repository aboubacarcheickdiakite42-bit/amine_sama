"""
Gestion de l'état persistant du bot.
Suit les épisodes publiés par anime pour garantir la continuité.

Structure du fichier JSON :
{
  "animes": {
    "<mal_id>": {
      "title": "Nom de l'anime",
      "last_episode": 5,        # dernier épisode publié
      "started_at": "2026-...", # date de premier épisode publié
      "updated_at": "2026-..."  # date du dernier épisode publié
    }
  }
}
"""

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "published_animes.json")


def load_state() -> dict:
    """Charge l'état depuis le fichier JSON."""
    if not os.path.exists(STATE_FILE):
        return {"animes": {}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Migration : ancien format {"published": {...}} → nouveau format
            if "published" in data and "animes" not in data:
                logger.info("Migration de l'ancien état vers le nouveau format.")
                return {"animes": {}}
            return data
    except Exception as e:
        logger.warning(f"Impossible de charger l'état: {e}")
        return {"animes": {}}


def save_state(state: dict) -> None:
    """Sauvegarde l'état dans le fichier JSON."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Impossible de sauvegarder l'état: {e}")


def get_last_published_episode(mal_id: int) -> int:
    """
    Retourne le numéro du dernier épisode publié pour cet anime.
    Retourne 0 si aucun épisode n'a encore été publié.
    """
    state = load_state()
    key = str(mal_id)
    anime_state = state.get("animes", {}).get(key)
    if not anime_state:
        return 0
    return int(anime_state.get("last_episode", 0))


def mark_episode_published(mal_id: int, episode_num: int, title: str) -> None:
    """Marque un épisode comme publié."""
    state = load_state()
    key = str(mal_id)
    now = datetime.now().isoformat()

    if "animes" not in state:
        state["animes"] = {}

    if key not in state["animes"]:
        state["animes"][key] = {
            "title": title,
            "last_episode": episode_num,
            "started_at": now,
            "updated_at": now,
        }
    else:
        state["animes"][key]["last_episode"] = episode_num
        state["animes"][key]["updated_at"] = now
        state["animes"][key]["title"] = title

    save_state(state)
    logger.debug(f"Épisode marqué: {title} — EP{episode_num}")


def get_all_anime_states() -> dict:
    """Retourne l'état de tous les animes suivis."""
    return load_state().get("animes", {})


def get_published_count() -> int:
    """Retourne le nombre d'animes dont au moins un épisode a été publié."""
    return len(load_state().get("animes", {}))


def get_total_episodes_published() -> int:
    """Retourne le nombre total d'épisodes publiés (somme des last_episode)."""
    animes = load_state().get("animes", {})
    return sum(int(v.get("last_episode", 0)) for v in animes.values())


def cleanup_old_entries() -> int:
    """Supprime les entrées des animes terminés depuis plus de 90 jours."""
    from datetime import timedelta
    state = load_state()
    animes = state.get("animes", {})
    cutoff = datetime.now() - timedelta(days=90)
    to_delete = []

    for key, data in animes.items():
        try:
            updated = datetime.fromisoformat(data.get("updated_at", ""))
            if updated < cutoff:
                to_delete.append(key)
        except Exception:
            pass

    for key in to_delete:
        del animes[key]

    if to_delete:
        state["animes"] = animes
        save_state(state)
        logger.info(f"Nettoyé {len(to_delete)} animes anciens")

    return len(to_delete)
