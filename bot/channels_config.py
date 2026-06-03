"""
Gestion de la configuration des canaux sources.
Les canaux sont sauvegardés dans un fichier JSON local.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

CHANNELS_FILE = os.path.join(os.path.dirname(__file__), "source_channels.json")


def load_channels() -> list[str]:
    """Charge la liste des canaux sources."""
    if not os.path.exists(CHANNELS_FILE):
        return []
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("channels", [])
    except Exception as e:
        logger.warning(f"Impossible de charger les canaux: {e}")
        return []


def save_channels(channels: list[str]) -> None:
    """Sauvegarde la liste des canaux sources."""
    try:
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump({"channels": channels}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Impossible de sauvegarder les canaux: {e}")


def add_channel(channel: str) -> bool:
    """Ajoute un canal source. Retourne True si ajouté, False si déjà présent."""
    channels = load_channels()
    # Normaliser le nom du canal
    channel = channel.strip().rstrip("/").split("/")[-1]
    if not channel.startswith("@"):
        channel = "@" + channel if not channel.lstrip("-").isdigit() else channel

    if channel in channels:
        return False
    channels.append(channel)
    save_channels(channels)
    logger.info(f"Canal ajouté: {channel}")
    return True


def remove_channel(channel: str) -> bool:
    """Supprime un canal source. Retourne True si supprimé."""
    channels = load_channels()
    channel = channel.strip()
    if not channel.startswith("@") and not channel.lstrip("-").isdigit():
        channel = "@" + channel

    if channel not in channels:
        return False
    channels.remove(channel)
    save_channels(channels)
    logger.info(f"Canal supprimé: {channel}")
    return True


def get_channels_count() -> int:
    return len(load_channels())


# --- Gestion des mots-clés de filtre ---

KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), "filter_keywords.json")

DEFAULT_KEYWORDS = ["vf", "french", "vf ", " vf", "vostfr"]


def load_keywords() -> list[str]:
    """Charge les mots-clés de filtre. Retourne les défauts si pas de fichier."""
    if not os.path.exists(KEYWORDS_FILE):
        return []  # Pas de filtre par défaut → tout passe
    try:
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("keywords", [])
    except Exception as e:
        logger.warning(f"Impossible de charger les mots-clés: {e}")
        return []


def save_keywords(keywords: list[str]) -> None:
    """Sauvegarde les mots-clés de filtre."""
    try:
        with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump({"keywords": keywords}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Impossible de sauvegarder les mots-clés: {e}")


def set_keywords(keywords: list[str]) -> None:
    """Remplace tous les mots-clés par la nouvelle liste."""
    save_keywords([kw.lower().strip() for kw in keywords if kw.strip()])


def clear_keywords() -> None:
    """Supprime tous les filtres (tout passe)."""
    save_keywords([])
