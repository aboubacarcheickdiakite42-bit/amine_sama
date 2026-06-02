"""
Configuration Telethon — corrige automatiquement si API_ID et API_HASH sont inversés.
"""

import os

def get_telethon_credentials() -> tuple[int, str, str]:
    """
    Retourne (api_id, api_hash, phone) en corrigeant automatiquement
    si les valeurs API_ID et API_HASH ont été saisies dans le mauvais champ.
    """
    raw_id = os.environ.get("TELEGRAM_API_ID", "").strip()
    raw_hash = os.environ.get("TELEGRAM_API_HASH", "").strip()
    phone = os.environ.get("TELEGRAM_PHONE", "").strip()

    # Détection et correction automatique si les valeurs sont inversées
    # L'API_ID est toujours un nombre, l'API_HASH est toujours hexadécimal de 32 chars
    if raw_id.isdigit() and not raw_hash.isdigit():
        # Ordre correct
        api_id = int(raw_id)
        api_hash = raw_hash.lower()
    elif raw_hash.isdigit() and not raw_id.isdigit():
        # Inversé — on corrige
        api_id = int(raw_hash)
        api_hash = raw_id.lower()
    else:
        # Fallback
        api_id = int(raw_id) if raw_id.isdigit() else 0
        api_hash = raw_hash.lower()

    return api_id, api_hash, phone
