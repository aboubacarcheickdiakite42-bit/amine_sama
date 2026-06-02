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
