"""
Module de publication des animes sur le canal Telegram.
"""

import os
import logging
import asyncio
from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]


def format_anime_message(anime: dict) -> str:
    """Formate un anime en message Telegram bien présenté."""
    lines = []

    # Titre principal
    title = anime.get("title", "Titre inconnu")
    title_jp = anime.get("title_jp", "")
    lines.append(f"🎌 <b>{title}</b>")
    if title_jp and title_jp != title:
        lines.append(f"<i>{title_jp}</i>")

    lines.append("")

    # Badge langue + saison
    lang = anime.get("lang", "VF")
    season = anime.get("season", "")
    badge_parts = [f"🇫🇷 <b>{lang}</b>"]
    if season:
        badge_parts.append(f"📅 {season}")
    lines.append(" | ".join(badge_parts))

    # Infos clés
    score = anime.get("score")
    episodes = anime.get("episodes")
    status = anime.get("status", "")
    studio = anime.get("studio", "")

    info_parts = []
    if score:
        info_parts.append(f"⭐ {score}/10")
    if episodes:
        info_parts.append(f"📺 {episodes} éps")
    elif status:
        info_parts.append(f"📺 {status}")
    if studio:
        info_parts.append(f"🏢 {studio}")

    if info_parts:
        lines.append(" | ".join(info_parts))

    # Genres
    genres = anime.get("genres", [])
    if genres:
        genre_tags = " ".join([f"#{g.replace(' ', '').replace('-', '')}" for g in genres])
        lines.append(f"🏷️ {genre_tags}")

    # Synopsis
    synopsis = anime.get("synopsis", "")
    if synopsis:
        lines.append("")
        lines.append(f"📖 {synopsis}")

    # Lien
    url = anime.get("url", "")
    if url:
        lines.append("")
        lines.append(f'🔗 <a href="{url}">Voir sur MyAnimeList</a>')

    lines.append("")
    lines.append("#Anime #VF #NouvellesSorties")

    return "\n".join(lines)


async def send_anime_async(anime: dict) -> bool:
    """Envoie un anime sur le canal Telegram de manière asynchrone."""
    bot = Bot(token=BOT_TOKEN)
    message = format_anime_message(anime)
    image_url = anime.get("image")

    try:
        if image_url:
            try:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=message,
                    parse_mode=ParseMode.HTML,
                )
                logger.info(f"✅ Publié avec image: {anime.get('title')}")
                return True
            except TelegramError as e:
                logger.warning(f"Image échouée, tentative texte seul: {e}")

        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False,
        )
        logger.info(f"✅ Publié (texte): {anime.get('title')}")
        return True

    except TelegramError as e:
        logger.error(f"❌ Erreur publication Telegram: {e}")
        return False
    finally:
        await bot.close()


def send_anime(anime: dict) -> bool:
    """Wrapper synchrone pour envoyer un anime."""
    return asyncio.run(send_anime_async(anime))


async def send_status_message_async(text: str) -> bool:
    """Envoie un message de statut sur le canal."""
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        return True
    except TelegramError as e:
        logger.error(f"Erreur message statut: {e}")
        return False
    finally:
        await bot.close()


def send_status_message(text: str) -> bool:
    """Wrapper synchrone pour envoyer un message de statut."""
    return asyncio.run(send_status_message_async(text))
