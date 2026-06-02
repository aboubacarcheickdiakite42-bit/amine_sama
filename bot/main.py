"""
Bot Telegram - Anime VF Tracker
Publie automatiquement les nouveaux animes VF disponibles sur votre canal.
Supporte les commandes : /stats, /next, /forcecycle, /help
"""

import os
import logging
import time
import asyncio
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from telegram.ext import Application, CommandHandler

from scraper import get_latest_anime_vf
from publisher import send_anime
from state import is_already_published, mark_as_published, cleanup_old_entries, get_published_count
from commands import cmd_stats, cmd_forcecycle, cmd_next, cmd_help, set_scheduler

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))
ANIMES_PER_CYCLE = int(os.environ.get("ANIMES_PER_CYCLE", "3"))
PUBLISH_DELAY_SECONDS = int(os.environ.get("PUBLISH_DELAY_SECONDS", "5"))


def run_cycle():
    """Un cycle complet : scraping + publication des nouveautés."""
    logger.info(f"=== Début du cycle — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")

    try:
        animes = get_latest_anime_vf(max_results=20)
        logger.info(f"Récupéré {len(animes)} animes depuis les sources")

        if not animes:
            logger.warning("Aucun anime trouvé dans ce cycle")
            return

        new_animes = [a for a in animes if not is_already_published(a["title"])]
        logger.info(f"{len(new_animes)} nouveaux animes à publier (sur {len(animes)} trouvés)")

        if not new_animes:
            logger.info("Aucune nouveauté — tout a déjà été publié")
            return

        published_count = 0
        for anime in new_animes[:ANIMES_PER_CYCLE]:
            title = anime.get("title", "?")
            logger.info(f"Publication de: {title}")

            success = send_anime(anime)
            if success:
                mark_as_published(title)
                published_count += 1
                if published_count < ANIMES_PER_CYCLE:
                    time.sleep(PUBLISH_DELAY_SECONDS)
            else:
                logger.error(f"Échec de publication pour: {title}")

        logger.info(f"=== Cycle terminé — {published_count} anime(s) publié(s) ===")

    except Exception as e:
        logger.error(f"Erreur inattendue dans le cycle: {e}", exc_info=True)


def main():
    logger.info("🚀 Bot Anime VF Telegram démarré")
    logger.info(f"📡 Canal cible: {os.environ.get('TELEGRAM_CHANNEL_ID', '?')}")
    logger.info(f"⏱️  Vérification toutes les {CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"📦 Jusqu'à {ANIMES_PER_CYCLE} animes par cycle")

    # Nettoyage au démarrage
    cleaned = cleanup_old_entries()
    total = get_published_count()
    logger.info(f"📂 État: {total} animes en mémoire ({cleaned} anciens supprimés)")

    # Scheduler en arrière-plan (non bloquant)
    scheduler = BackgroundScheduler(timezone="Europe/Paris")
    scheduler.add_job(
        run_cycle,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL_MINUTES),
        id="anime_vf_cycle",
        name="Cycle Anime VF",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    # Injecter le scheduler dans les commandes
    set_scheduler(scheduler)

    # Premier cycle immédiat
    logger.info("▶️  Premier cycle immédiat...")
    run_cycle()

    logger.info(f"⏰ Prochain cycle dans {CHECK_INTERVAL_MINUTES} minutes")
    logger.info("🎮 Démarrage du listener de commandes Telegram...")

    # Application Telegram pour les commandes
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("forcecycle", cmd_forcecycle))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))

    logger.info("✅ Commandes disponibles : /stats /next /forcecycle /help")

    try:
        app.run_polling(drop_pending_updates=True)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot arrêté proprement.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
