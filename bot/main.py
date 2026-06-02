"""
Bot Anime VF — Transfert automatique
Surveille des canaux Telegram sources et transfère les vidéos vers votre canal,
en supprimant les références aux canaux sources.
"""

import os
import sys
import logging
import asyncio
import threading

from channels_config import load_channels
from forwarder import run_userbot
from bot_commands import create_bot_app
from state_forwarder import cleanup_old_forwarded

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_command_bot():
    """Lance le bot de commandes dans un thread séparé."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = create_bot_app()
    logger.info("🎮 Bot de commandes démarré")
    app.run_polling(drop_pending_updates=True)


async def main():
    logger.info("🚀 Bot Anime VF — Transfert automatique démarré")
    logger.info(f"📡 Canal cible: {os.environ.get('TELEGRAM_CHANNEL_ID', '?')}")

    # Nettoyage des vieux messages
    cleaned = cleanup_old_forwarded()
    if cleaned:
        logger.info(f"🧹 {cleaned} anciens messages nettoyés")

    channels = load_channels()
    if channels:
        logger.info(f"📡 Canaux sources: {', '.join(channels)}")
    else:
        logger.info("⚠️  Aucun canal source — envoyez /addcanal @nomcanal à votre bot pour en ajouter")

    # Lancer le bot de commandes dans un thread séparé
    cmd_thread = threading.Thread(target=run_command_bot, daemon=True)
    cmd_thread.start()
    logger.info("✅ Bot de commandes lancé en arrière-plan")

    # Lancer le userbot Telethon (bloquant)
    await run_userbot(load_channels)


if __name__ == "__main__":
    asyncio.run(main())
