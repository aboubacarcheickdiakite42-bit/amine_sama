"""
Bot Anime VF — Transfert automatique
Surveille des canaux Telegram sources et transfère les vidéos vers votre canal.
Tout tourne dans le même event loop asyncio pour éviter les conflits.
"""

import os
import logging
import asyncio

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


async def run_command_bot_async(app):
    """Lance le bot de commandes de manière asynchrone."""
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("🎮 Bot de commandes démarré")


async def main():
    logger.info("🚀 Bot Anime VF — Transfert automatique démarré")
    logger.info(f"📡 Canal cible: {os.environ.get('TELEGRAM_CHANNEL_ID', '?')}")

    cleaned = cleanup_old_forwarded()
    if cleaned:
        logger.info(f"🧹 {cleaned} anciens messages nettoyés")

    channels = load_channels()
    if channels:
        logger.info(f"📡 Canaux sources: {', '.join(channels)}")
    else:
        logger.info("⚠️  Aucun canal source — envoyez /addcanal @nomcanal à votre bot pour en ajouter")

    # Lancer le bot de commandes en tâche de fond
    app = create_bot_app()
    asyncio.create_task(run_command_bot_async(app))

    # Lancer le userbot Telethon (bloquant jusqu'à déconnexion)
    await run_userbot(load_channels)

    # Arrêt propre
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
