"""
Module de publication des épisodes d'anime sur le canal Telegram.
"""

import os
import logging
import asyncio
import time
from telegram import Bot
from telegram.error import TelegramError, RetryAfter
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]


def format_episode_message(anime: dict, episode: dict) -> str:
    """Formate un épisode en message Telegram bien présenté."""
    lines = []

    title = anime.get("title", "Titre inconnu")
    title_jp = anime.get("title_jp", "")
    ep_num = episode.get("episode_num", "?")
    ep_title = episode.get("title", "")
    total_eps = anime.get("total_episodes")

    # En-tête : titre de l'anime
    lines.append(f"🎌 <b>{title}</b>")
    if title_jp and title_jp != title:
        lines.append(f"<i>{title_jp}</i>")

    lines.append("")

    # Numéro d'épisode
    ep_label = f"Épisode {ep_num}"
    if total_eps:
        ep_label += f" / {total_eps}"
    lines.append(f"📺 <b>{ep_label}</b>")

    if ep_title and ep_title != f"Épisode {ep_num}" and ep_title.lower() != title.lower():
        lines.append(f"<i>« {ep_title} »</i>")

    lines.append("")

    # Badges
    lang = anime.get("lang", "VF")
    season = anime.get("season", "")
    badge_parts = [f"🇫🇷 <b>{lang}</b>"]
    if season:
        badge_parts.append(f"📅 {season}")
    lines.append(" | ".join(badge_parts))

    # Infos de l'anime
    score = anime.get("score")
    studio = anime.get("studio", "")
    info_parts = []
    if score:
        info_parts.append(f"⭐ {score}/10")
    if studio:
        info_parts.append(f"🏢 {studio}")
    if info_parts:
        lines.append(" | ".join(info_parts))

    # Genres
    genres = anime.get("genres", [])
    if genres:
        genre_tags = " ".join([f"#{g.replace(' ', '').replace('-', '')}" for g in genres])
        lines.append(f"🏷️ {genre_tags}")

    # Synopsis (seulement pour l'épisode 1)
    if ep_num == 1:
        synopsis = anime.get("synopsis", "")
        if synopsis:
            lines.append("")
            lines.append(f"📖 {synopsis}")

    # Filler / recap
    if episode.get("filler"):
        lines.append("")
        lines.append("⚠️ <i>Épisode filler</i>")
    elif episode.get("recap"):
        lines.append("")
        lines.append("⚠️ <i>Épisode récapitulatif</i>")

    # Lien MAL
    url = anime.get("url", "")
    if url:
        lines.append("")
        lines.append(f'🔗 <a href="{url}">Voir sur MyAnimeList</a>')

    lines.append("")

    # Hashtags
    hashtags = ["#Anime", f"#VF", f"#{title.replace(' ', '').replace(':', '').replace('-', '')[:20]}"]
    if genres:
        hashtags += [f"#{g.replace(' ', '').replace('-', '')}" for g in genres[:2]]
    lines.append(" ".join(hashtags))

    return "\n".join(lines)


async def send_episode_async(anime: dict, episode: dict, retries: int = 3) -> bool:
    """Publie un épisode sur le canal Telegram avec gestion du rate-limit."""
    bot = Bot(token=BOT_TOKEN)
    message = format_episode_message(anime, episode)
    image_url = anime.get("image")

    for attempt in range(1, retries + 1):
        try:
            if image_url:
                try:
                    await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=image_url,
                        caption=message,
                        parse_mode=ParseMode.HTML,
                    )
                    logger.info(f"✅ Publié avec image: {anime.get('title')} EP{episode.get('episode_num')}")
                    return True
                except RetryAfter:
                    raise
                except TelegramError as e:
                    logger.warning(f"Image échouée, tentative texte seul: {e}")

            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            logger.info(f"✅ Publié (texte): {anime.get('title')} EP{episode.get('episode_num')}")
            return True

        except RetryAfter as e:
            wait = int(e.retry_after) + 2
            logger.warning(f"⏳ Rate-limit Telegram — attente de {wait}s (tentative {attempt}/{retries})")
            await asyncio.sleep(wait)
        except TelegramError as e:
            logger.error(f"❌ Erreur Telegram (tentative {attempt}/{retries}): {e}")
            if attempt < retries:
                await asyncio.sleep(3)

    logger.error(f"❌ Échec définitif: {anime.get('title')} EP{episode.get('episode_num')}")
    try:
        await bot.close()
    except Exception:
        pass
    return False


def send_episode(anime: dict, episode: dict) -> bool:
    """Wrapper synchrone pour publier un épisode."""
    return asyncio.run(send_episode_async(anime, episode))
