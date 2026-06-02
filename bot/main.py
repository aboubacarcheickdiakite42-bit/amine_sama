"""
Bot Telegram - Anime VF Tracker
Publie automatiquement les épisodes d'animes VF épisode par épisode,
en commençant toujours par l'épisode 1 si l'anime n'a pas encore été démarré.
"""

import os
import logging
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from telegram.ext import Application, CommandHandler

from scraper import get_seasonal_animes, get_next_episode_to_publish
from publisher import send_episode
from state import (
    get_last_published_episode,
    mark_episode_published,
    cleanup_old_entries,
    get_published_count,
    get_total_episodes_published,
)
from commands import cmd_stats, cmd_forcecycle, cmd_next, cmd_help, set_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))
EPISODES_PER_CYCLE = int(os.environ.get("ANIMES_PER_CYCLE", "3"))
PUBLISH_DELAY_SECONDS = int(os.environ.get("PUBLISH_DELAY_SECONDS", "8"))


def run_cycle():
    """
    Cycle principal :
    1. Récupère les animes de la saison actuelle
    2. Pour chaque anime, vérifie le dernier épisode publié
    3. Publie le prochain épisode disponible en commençant par EP1 si l'anime est nouveau
    """
    logger.info(f"=== Début du cycle — {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")

    try:
        animes = get_seasonal_animes(limit=25)
        if not animes:
            logger.warning("Aucun anime récupéré depuis Jikan")
            return

        published_this_cycle = 0

        for anime in animes:
            if published_this_cycle >= EPISODES_PER_CYCLE:
                break

            mal_id = anime["mal_id"]
            title = anime["title"]

            # Trouver le dernier épisode publié pour cet anime (0 = jamais publié)
            last_ep = get_last_published_episode(mal_id)
            next_ep_num = last_ep + 1

            logger.info(f"[{title}] Dernier EP publié: {last_ep} → Cherche EP{next_ep_num}")

            # Récupérer le prochain épisode disponible
            episode = get_next_episode_to_publish(mal_id, last_ep)

            if not episode:
                logger.info(f"[{title}] Aucun nouvel épisode disponible (EP{next_ep_num} pas encore sorti)")
                continue

            actual_ep_num = episode["episode_num"]
            if actual_ep_num != next_ep_num:
                logger.info(f"[{title}] EP{next_ep_num} introuvable, prochain disponible: EP{actual_ep_num}")

            logger.info(f"[{title}] Publication EP{actual_ep_num}...")
            success = send_episode(anime, episode)

            if success:
                mark_episode_published(mal_id, actual_ep_num, title)
                published_this_cycle += 1
                logger.info(f"✅ [{title}] EP{actual_ep_num} publié avec succès")

                if published_this_cycle < EPISODES_PER_CYCLE:
                    time.sleep(PUBLISH_DELAY_SECONDS)
            else:
                logger.error(f"❌ [{title}] Échec publication EP{actual_ep_num}")

        logger.info(f"=== Cycle terminé — {published_this_cycle} épisode(s) publié(s) ===")

    except Exception as e:
        logger.error(f"Erreur inattendue dans le cycle: {e}", exc_info=True)


def main():
    logger.info("🚀 Bot Anime VF Telegram démarré")
    logger.info(f"📡 Canal cible: {os.environ.get('TELEGRAM_CHANNEL_ID', '?')}")
    logger.info(f"⏱️  Vérification toutes les {CHECK_INTERVAL_MINUTES} minutes")
    logger.info(f"📦 Jusqu'à {EPISODES_PER_CYCLE} épisodes par cycle")

    cleaned = cleanup_old_entries()
    total_animes = get_published_count()
    total_eps = get_total_episodes_published()
    logger.info(f"📂 État: {total_animes} animes suivis, {total_eps} épisodes publiés ({cleaned} anciens supprimés)")

    # Scheduler en arrière-plan
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

    set_scheduler(scheduler)

    # Premier cycle immédiat
    logger.info("▶️  Premier cycle immédiat...")
    run_cycle()

    logger.info(f"⏰ Prochain cycle dans {CHECK_INTERVAL_MINUTES} minutes")
    logger.info("🎮 Démarrage du listener de commandes Telegram...")

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
