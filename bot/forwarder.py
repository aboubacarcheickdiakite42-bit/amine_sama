"""
Moteur de transfert Telethon.
Se connecte comme un vrai compte Telegram, surveille les canaux sources,
et transfère les messages vidéo vers le canal cible en supprimant les références sources.
"""

import os
import logging
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import (
    MessageMediaDocument,
    MessageMediaPhoto,
    DocumentAttributeVideo,
    DocumentAttributeFilename,
)
from telethon.errors import FloodWaitError

logger = logging.getLogger(__name__)

from config import get_telethon_credentials
API_ID, API_HASH, PHONE = get_telethon_credentials()
TARGET_CHANNEL = os.environ["TELEGRAM_CHANNEL_ID"]

SESSION_FILE = os.path.join(os.path.dirname(__file__), "userbot_session")


def is_video_message(message) -> bool:
    """Vérifie si un message contient un fichier vidéo."""
    if not message.media:
        return False

    if isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if not doc:
            return False
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeVideo):
                return True
            if isinstance(attr, DocumentAttributeFilename):
                fname = attr.file_name.lower()
                if any(fname.endswith(ext) for ext in [".mp4", ".mkv", ".avi", ".mov", ".webm"]):
                    return True
        if hasattr(doc, "mime_type") and doc.mime_type:
            if "video" in doc.mime_type:
                return True

    return False


def get_message_text_content(message) -> str:
    """Extrait tout le texte disponible d'un message (caption, nom de fichier, texte)."""
    parts = []
    if message.text:
        parts.append(message.text)
    if message.media and isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if doc:
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    parts.append(attr.file_name)
    return " ".join(parts).lower()


def passes_keyword_filter(message) -> tuple[bool, str]:
    """
    Vérifie si un message passe le filtre de mots-clés VF.
    Retourne (True, raison) si accepté, (False, raison) si rejeté.
    Si aucun filtre n'est configuré, tout passe.
    """
    from channels_config import load_keywords
    keywords = load_keywords()

    # Aucun filtre configuré → tout passe
    if not keywords:
        return True, "pas de filtre"

    content = get_message_text_content(message)
    for kw in keywords:
        if kw.lower() in content:
            return True, f"mot-clé '{kw}' trouvé"

    return False, f"aucun mot-clé trouvé dans: {content[:80]}"


def clean_caption(text: str, source_channel: str) -> str | None:
    """
    Nettoie le texte d'un message :
    - Supprime les mentions du canal source (@canal, t.me/canal, liens)
    - Retourne None si le texte est vide après nettoyage
    """
    if not text:
        return None

    import re

    # Supprimer les lignes contenant des mentions de canaux
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        # Ignorer les lignes avec @mention, t.me/, telegram.me/
        if re.search(r"@\w+|t\.me/|telegram\.me/|Rejoindre|Join|Source|Canal|Channel", line, re.IGNORECASE):
            continue
        clean_lines.append(line)

    result = "\n".join(clean_lines).strip()
    # Supprimer les lignes vides en double
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result if result else None


async def forward_message(client: TelegramClient, message, source_channel: str) -> bool:
    """
    Transfère un message vidéo vers le canal cible.
    Re-envoie le fichier (sans forward tag) pour ne pas montrer la source.
    """
    try:
        caption = clean_caption(message.text or message.caption or "", source_channel)

        # Télécharger et renvoyer le fichier pour éviter le "forwarded from"
        await client.send_file(
            TARGET_CHANNEL,
            file=message.media,
            caption=caption,
            supports_streaming=True,
            force_document=False,
        )
        logger.info(f"✅ Vidéo transférée depuis {source_channel}")
        return True

    except FloodWaitError as e:
        logger.warning(f"⏳ FloodWait — attente {e.seconds}s")
        await asyncio.sleep(e.seconds + 1)
        return False
    except Exception as e:
        logger.error(f"❌ Erreur transfert: {e}", exc_info=True)
        return False


async def scan_and_forward_history(client: TelegramClient, source_channel: str, limit: int = 50) -> int:
    """
    Parcourt l'historique récent d'un canal source et transfère
    les vidéos qui passent le filtre de mots-clés.
    """
    from state_forwarder import is_message_forwarded, mark_message_forwarded, is_paused

    if is_paused():
        logger.info(f"[{source_channel}] ⏸️ Bot en pause — scan ignoré")
        return 0

    forwarded = 0
    skipped = 0
    try:
        entity = await client.get_entity(source_channel)
        async for message in client.iter_messages(entity, limit=limit):
            if not is_video_message(message):
                continue

            msg_key = f"{source_channel}:{message.id}"
            if is_message_forwarded(msg_key):
                continue

            # Vérifier le filtre mots-clés
            passed, reason = passes_keyword_filter(message)
            if not passed:
                logger.info(f"[{source_channel}] ⏭️ Ignoré (filtre): {reason}")
                skipped += 1
                continue

            logger.info(f"[{source_channel}] ✅ Vidéo acceptée ({reason}): ID {message.id}")
            success = await forward_message(client, message, source_channel)
            if success:
                mark_message_forwarded(msg_key)
                forwarded += 1
                await asyncio.sleep(3)

    except Exception as e:
        logger.error(f"Erreur scan {source_channel}: {e}")

    if skipped:
        logger.info(f"[{source_channel}] {skipped} vidéo(s) ignorée(s) par le filtre")
    return forwarded


async def run_userbot(source_channels_getter):
    """
    Lance le userbot Telethon :
    1. Écoute les nouveaux messages en temps réel sur les canaux sources
    2. Scanne aussi l'historique récent au démarrage
    """
    from state_forwarder import is_message_forwarded, mark_message_forwarded

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    await client.start(phone=PHONE)
    me = await client.get_me()
    logger.info(f"✅ Connecté en tant que: {me.first_name} (@{me.username})")

    # Scan initial de l'historique récent de chaque canal
    channels = source_channels_getter()
    if channels:
        logger.info(f"📡 Scan initial de {len(channels)} canal(aux) source(s)...")
        for ch in channels:
            count = await scan_and_forward_history(client, ch, limit=30)
            logger.info(f"[{ch}] {count} vidéo(s) transférée(s) depuis l'historique")
            await asyncio.sleep(2)
    else:
        logger.info("⚠️  Aucun canal source configuré. Utilisez /addcanal pour en ajouter.")

    # Listener temps réel pour les nouveaux messages
    @client.on(events.NewMessage())
    async def on_new_message(event):
        channels_now = source_channels_getter()
        if not channels_now:
            return

        try:
            chat = await event.get_chat()
            chat_username = getattr(chat, "username", None)
            chat_id = str(event.chat_id)

            # Vérifier si le message vient d'un canal source
            is_from_source = False
            matched_channel = None
            for ch in channels_now:
                ch_clean = ch.lstrip("@").lower()
                if (chat_username and chat_username.lower() == ch_clean) or chat_id == ch:
                    is_from_source = True
                    matched_channel = ch
                    break

            if not is_from_source:
                return

            if not is_video_message(event.message):
                return

            # Vérifier l'état pause
            from state_forwarder import is_paused
            if is_paused():
                logger.info(f"🔔 [{matched_channel}] ⏸️ Bot en pause — message ignoré")
                return

            msg_key = f"{matched_channel}:{event.message.id}"
            if is_message_forwarded(msg_key):
                return

            # Vérifier le filtre mots-clés
            passed, reason = passes_keyword_filter(event.message)
            if not passed:
                logger.info(f"🔔 [{matched_channel}] Vidéo ignorée (filtre): {reason}")
                return

            logger.info(f"🔔 Nouveau message vidéo depuis {matched_channel} ({reason})")
            success = await forward_message(client, event.message, matched_channel)
            if success:
                mark_message_forwarded(msg_key)

        except Exception as e:
            logger.error(f"Erreur handler nouveau message: {e}")

    logger.info("👂 Écoute des nouveaux messages en cours...")
    await client.run_until_disconnected()
