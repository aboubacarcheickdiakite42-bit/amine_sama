"""
Bot Telegram - Anime VF Tracker
Publie automatiquement les nouveaux animes VF disponibles sur votre canal.
"""

import os
import logging
import time
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from scraper import get_latest_anime_vf
from publisher import send_anime, send_status_message
from state import is_already_published, mark_as_published, cleanup_old_entries, get_published_count

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Intervalle de vérification (en minutes)
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))
# Nombre d'animes à publier par cycle
ANIMES_PER_CYCLE = int(os.environ.get("ANIMES_PER_CYCLE", "3"))
# Délai entre chaque publication (secondes) pour éviter le spam
PUBLISH_DELAY_SECONDS = int(os.environ.get("PUBLISH_DELAY_SECONDS", "5"))


def run_cycle():
    """Un cycle complet : scraping + publication des nouveautés."""
    logger.info(f"=== Début du cycle — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")

    try:
        # Récupérer les derniers animes VF
        animes = get_latest_anime_vf(max_results=20)
        logger.info(f"Récupéré {len(animes)} animes depuis les sources")

        if not animes:
            logger.warning("Aucun anime trouvé dans ce cycle")
            return

        # Filtrer ceux déjà publiés
        new_animes = [a for a in animes if not is_already_published(a["title"])]
        logger.info(f"{len(new_animes)} nouveaux animes à publier (sur {len(animes)} trouvés)")

        if not new_animes:
            logger.info("Aucune nouveauté — tout a déjà été publié")
            return

        # Publier au maximum ANIMES_PER_CYCLE animes par cycle
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

    # Nettoyage des vieilles entrées au démarrage
    cleaned = cleanup_old_entries()
    total = get_published_count()
    logger.info(f"📂 État: {total} animes en mémoire ({cleaned} anciens supprimés)")

    # Premier cycle immédiat au démarrage
    logger.info("▶️  Premier cycle immédiat...")
    run_cycle()

    # Scheduler pour les cycles suivants
    scheduler = BlockingScheduler(timezone="Europe/Paris")
    scheduler.add_job(
        run_cycle,
        trigger=IntervalTrigger(minutes=CHECK_INTERVAL_MINUTES),
        id="anime_vf_cycle",
        name="Cycle Anime VF",
        max_instances=1,
        coalesce=True,
    )

    logger.info(f"⏰ Prochain cycle dans {CHECK_INTERVAL_MINUTES} minutes")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot arrêté proprement.")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
