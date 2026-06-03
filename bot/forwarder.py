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


def get_filename(message) -> str | None:
    """Extrait le nom de fichier d'un message vidéo."""
    if message.media and isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if doc:
            for attr in doc.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    return attr.file_name
    return None


def passes_keyword_filter(message) -> tuple[bool, str]:
    """
    Vérifie si un message passe le filtre VF.
    Règle fixe : VOSTFR est TOUJOURS rejeté, peu importe les mots-clés configurés.
    Si des mots-clés VF sont configurés, la vidéo doit en contenir un.
    """
    from channels_config import load_keywords
    from series_utils import is_vostfr, is_vf

    content = get_message_text_content(message)

    # Règle 1 (fixe) : bloquer VOSTFR quoi qu'il arrive
    if is_vostfr(content):
        return False, f"contenu VOSTFR rejeté"

    keywords = load_keywords()

    # Aucun filtre configuré → tout passe (VOSTFR déjà bloqué ci-dessus)
    if not keywords:
        return True, "pas de filtre (non-VOSTFR)"

    # Avec filtre configuré : doit contenir un mot-clé
    for kw in keywords:
        if kw.lower() in content:
            return True, f"mot-clé '{kw}' trouvé"

    return False, f"aucun mot-clé VF trouvé"


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
    Vérifie la déduplication par nom de fichier avant l'envoi.
    """
    from state_forwarder import is_filename_published, mark_filename_published

    # Vérification anti-doublon par nom de fichier
    fname = get_filename(message)
    if fname:
        already, published_at = is_filename_published(fname)
        if already:
            date_str = published_at[:10] if published_at else "date inconnue"
            logger.info(f"⏭️ Doublon détecté '{fname}' — déjà publié le {date_str}")
            return False

    try:
        caption = clean_caption(message.text or "", source_channel)

        await client.send_file(
            TARGET_CHANNEL,
            file=message.media,
            caption=caption,
            supports_streaming=True,
            force_document=False,
        )

        # Enregistrer le nom de fichier après succès
        if fname:
            mark_filename_published(fname)

        logger.info(f"✅ Vidéo transférée depuis {source_channel}" + (f" ({fname})" if fname else ""))
        return True

    except FloodWaitError as e:
        logger.warning(f"⏳ FloodWait — attente {e.seconds}s")
        await asyncio.sleep(e.seconds + 1)
        return False
    except Exception as e:
        logger.error(f"❌ Erreur transfert: {e}", exc_info=True)
        return False


async def post_series_header(client: TelegramClient, series_key: str, series_title: str, cover_url: str | None = None) -> bool:
    """
    Poste une affiche/bannière avant le premier épisode d'une série.
    Essaie d'abord avec une image de couverture, sinon un message texte.
    """
    from state_forwarder import is_series_header_posted, mark_series_header_posted

    if is_series_header_posted(series_key):
        return False  # Déjà posté

    caption = f"🎬 <b>{series_title}</b>"

    try:
        if cover_url:
            await client.send_file(
                TARGET_CHANNEL,
                file=cover_url,
                caption=caption,
                parse_mode="html",
            )
            logger.info(f"🖼️ Affiche postée pour '{series_title}'")
        else:
            # Pas d'image → bannière texte
            banner = (
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎬 <b>{series_title}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━"
            )
            await client.send_message(TARGET_CHANNEL, banner, parse_mode="html")
            logger.info(f"📝 Bannière texte postée pour '{series_title}'")

        mark_series_header_posted(series_key)
        await asyncio.sleep(1)
        return True

    except Exception as e:
        logger.warning(f"⚠️ Impossible de poster l'affiche pour '{series_title}': {e}")
        return False


async def scan_and_forward_history(client: TelegramClient, source_channel: str, limit: int = 50) -> int:
    """
    Parcourt l'historique d'un canal source et transfère les vidéos VF.
    Stratégie :
    1. Collecte tous les messages vidéo VF du canal
    2. Groupe par série
    3. Poste en priorité les séries COMPLÈTES (EP01 → fin), avec affiche
    4. Puis les épisodes orphelins / séries incomplètes
    """
    from state_forwarder import is_message_forwarded, mark_message_forwarded, is_paused
    from series_utils import (
        group_messages_by_series, is_series_complete,
        get_series_title_clean, fetch_anime_cover, parse_series_info
    )

    if is_paused():
        logger.info(f"[{source_channel}] ⏸️ Bot en pause — scan ignoré")
        return 0

    forwarded = 0
    skipped = 0

    try:
        entity = await client.get_entity(source_channel)

        # Étape 1 : Collecter tous les messages vidéo VF non encore transférés
        candidates = []
        async for message in client.iter_messages(entity, limit=limit):
            if not is_video_message(message):
                continue
            msg_key = f"{source_channel}:{message.id}"
            if is_message_forwarded(msg_key):
                continue
            passed, reason = passes_keyword_filter(message)
            if not passed:
                logger.debug(f"[{source_channel}] Ignoré ({reason}): ID {message.id}")
                skipped += 1
                continue
            candidates.append(message)

        if not candidates:
            if skipped:
                logger.info(f"[{source_channel}] {skipped} vidéo(s) ignorée(s) (VOSTFR/filtre)")
            return 0

        logger.info(f"[{source_channel}] {len(candidates)} vidéo(s) VF à transférer, {skipped} ignorée(s)")

        # Étape 2 : Grouper par série
        groups, ungrouped = group_messages_by_series(candidates)

        # Étape 3 : Séparer séries complètes / incomplètes
        complete_series = {}
        incomplete_series = {}
        for key, episodes in groups.items():
            if is_series_complete(episodes):
                complete_series[key] = episodes
            else:
                incomplete_series[key] = episodes

        logger.info(
            f"[{source_channel}] Séries complètes: {len(complete_series)} | "
            f"Incomplètes: {len(incomplete_series)} | "
            f"Orphelins: {len(ungrouped)}"
        )

        async def send_episode(msg, series_key=None, series_info=None):
            nonlocal forwarded
            # Poster l'affiche avant le 1er épisode (EP01) d'une série
            if series_info and series_info["episode"] == 1 and series_key:
                title = get_series_title_clean(series_info)
                cover_url = await fetch_anime_cover(series_info["title"])
                await post_series_header(client, series_key, title, cover_url)

            success = await forward_message(client, msg, source_channel)
            if success:
                msg_key = f"{source_channel}:{msg.id}"
                mark_message_forwarded(msg_key)
                forwarded += 1
                await asyncio.sleep(2)

        # Étape 4a : Séries complètes EN PREMIER (dans l'ordre des épisodes)
        for key, episodes in complete_series.items():
            logger.info(f"[{source_channel}] 📺 Série complète: {key} ({len(episodes)} épisodes)")
            for ep_num, msg, info in episodes:
                await send_episode(msg, key, info)

        # Étape 4b : Séries incomplètes (dans l'ordre des épisodes)
        for key, episodes in incomplete_series.items():
            logger.info(f"[{source_channel}] 📺 Série incomplète: {key} ({len(episodes)} épisodes)")
            for ep_num, msg, info in episodes:
                await send_episode(msg, key, info)

        # Étape 4c : Épisodes orphelins (non reconnus par le parseur)
        for msg in ungrouped:
            await send_episode(msg)

    except Exception as e:
        logger.error(f"Erreur scan {source_channel}: {e}", exc_info=True)

    return forwarded


async def index_target_channel(client: TelegramClient, limit: int = 200) -> int:
    """
    Scanne l'historique du canal cible (@drofficielle) et indexe
    tous les noms de fichiers déjà publiés pour éviter les doublons futurs.
    """
    from state_forwarder import mark_filename_published, get_published_filenames_count

    before = get_published_filenames_count()
    indexed = 0
    try:
        entity = await client.get_entity(TARGET_CHANNEL)
        async for message in client.iter_messages(entity, limit=limit):
            if not is_video_message(message):
                continue
            fname = get_filename(message)
            if fname:
                mark_filename_published(fname)
                indexed += 1
        after = get_published_filenames_count()
        new_entries = after - before
        logger.info(f"📚 Index canal cible: {indexed} vidéos scannées, {new_entries} nouvelles entrées ({after} total)")
    except Exception as e:
        logger.warning(f"⚠️ Impossible d'indexer le canal cible: {e}")
    return indexed


async def run_userbot(source_channels_getter):
    """
    Lance le userbot Telethon :
    1. Indexe les vidéos déjà publiées dans le canal cible (anti-doublon)
    2. Scanne l'historique récent des canaux sources
    3. Écoute les nouveaux messages en temps réel
    """
    from state_forwarder import is_message_forwarded, mark_message_forwarded

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    await client.start(phone=PHONE)
    me = await client.get_me()
    logger.info(f"✅ Connecté en tant que: {me.first_name} (@{me.username})")

    # Indexer l'historique du canal cible pour la déduplication par nom de fichier
    logger.info(f"📚 Indexation du canal cible {TARGET_CHANNEL}...")
    await index_target_channel(client, limit=200)

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

            # Vérifier le filtre VF / bloquer VOSTFR
            passed, reason = passes_keyword_filter(event.message)
            if not passed:
                logger.info(f"🔔 [{matched_channel}] Ignoré ({reason})")
                return

            # Poster l'affiche si c'est le 1er épisode d'une nouvelle série
            from series_utils import parse_series_info, get_series_title_clean, fetch_anime_cover
            fname = get_filename(event.message)
            if fname:
                info = parse_series_info(fname)
                if info and info["episode"] == 1:
                    series_key = info["series_key"]
                    title = get_series_title_clean(info)
                    cover_url = await fetch_anime_cover(info["title"])
                    await post_series_header(client, series_key, title, cover_url)

            logger.info(f"🔔 Nouvel épisode VF depuis {matched_channel}: {fname or 'inconnu'}")
            success = await forward_message(client, event.message, matched_channel)
            if success:
                mark_message_forwarded(msg_key)

        except Exception as e:
            logger.error(f"Erreur handler nouveau message: {e}")

    logger.info("👂 Écoute des nouveaux messages en cours...")
    await client.run_until_disconnected()
