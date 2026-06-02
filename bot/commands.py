"""
Gestionnaire des commandes Telegram du bot.
"""

import logging
import os
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from state import get_published_count, load_state
from scraper import get_latest_anime_vf

logger = logging.getLogger(__name__)

CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))
ANIMES_PER_CYCLE = int(os.environ.get("ANIMES_PER_CYCLE", "3"))

# Référence partagée vers le scheduler (injectée depuis main.py)
_scheduler_ref = None
_bot_start_time = datetime.now()


def set_scheduler(scheduler):
    global _scheduler_ref
    _scheduler_ref = scheduler


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /stats — affiche les statistiques du bot."""
    try:
        state = load_state()
        published = state.get("published", {})
        total = len(published)

        # Calcul du dernier anime publié
        last_title = None
        last_time = None
        if published:
            latest = max(published.items(), key=lambda x: x[1])
            last_title = latest[0].title()
            try:
                last_time = datetime.fromisoformat(latest[1])
            except Exception:
                pass

        # Prochain cycle
        next_run = None
        if _scheduler_ref:
            job = _scheduler_ref.get_job("anime_vf_cycle")
            if job and job.next_run_time:
                next_run = job.next_run_time.replace(tzinfo=None)

        # Uptime du bot
        uptime = datetime.now() - _bot_start_time
        uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}min"

        lines = [
            "📊 <b>Statistiques du Bot Anime VF</b>",
            "",
            f"🎌 <b>Animes publiés :</b> {total}",
        ]

        if last_title:
            lines.append(f"🕐 <b>Dernier publié :</b> {last_title}")
            if last_time:
                lines.append(f"   <i>{last_time.strftime('%d/%m/%Y à %H:%M')}</i>")

        lines.append("")
        lines.append(f"⏱️ <b>Intervalle de vérification :</b> {CHECK_INTERVAL_MINUTES} min")
        lines.append(f"📦 <b>Animes par cycle :</b> {ANIMES_PER_CYCLE}")

        if next_run:
            diff = next_run - datetime.now()
            mins = max(0, int(diff.total_seconds() // 60))
            lines.append(f"⏰ <b>Prochain cycle dans :</b> {mins} minute(s)")

        lines.append(f"🟢 <b>Bot en ligne depuis :</b> {uptime_str}")
        lines.append("")
        lines.append("Utilisez /forcecycle pour lancer un cycle immédiatement.")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"Commande /stats utilisée par {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Erreur /stats: {e}", exc_info=True)
        await update.message.reply_text("❌ Erreur lors de la récupération des statistiques.")


async def cmd_forcecycle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /forcecycle — déclenche un cycle de publication immédiat."""
    try:
        await update.message.reply_text("⚙️ Lancement d'un cycle immédiat... Cela peut prendre quelques secondes.")

        if _scheduler_ref:
            job = _scheduler_ref.get_job("anime_vf_cycle")
            if job:
                _scheduler_ref.modify_job("anime_vf_cycle", next_run_time=datetime.now())
                await update.message.reply_text("✅ Cycle lancé ! Consultez votre canal pour les nouvelles publications.")
                logger.info(f"Cycle forcé par {update.effective_user.id}")
                return

        await update.message.reply_text("⚠️ Impossible de forcer le cycle (scheduler non disponible).")

    except Exception as e:
        logger.error(f"Erreur /forcecycle: {e}", exc_info=True)
        await update.message.reply_text("❌ Erreur lors du lancement du cycle.")


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /next — affiche les prochains animes qui pourraient être publiés."""
    try:
        await update.message.reply_text("🔍 Recherche des prochains animes VF disponibles...")

        from state import is_already_published
        animes = get_latest_anime_vf(max_results=10)
        new_animes = [a for a in animes if not is_already_published(a["title"])]

        if not new_animes:
            await update.message.reply_text("✅ Aucun nouvel anime en attente — tout a déjà été publié !")
            return

        lines = [f"🎌 <b>{len(new_animes)} anime(s) en attente de publication :</b>", ""]
        for i, a in enumerate(new_animes[:8], 1):
            score = f" ⭐{a['score']}" if a.get("score") else ""
            genres = ", ".join(a.get("genres", [])[:2])
            genre_str = f" — {genres}" if genres else ""
            lines.append(f"{i}. <b>{a['title']}</b>{score}{genre_str}")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"Commande /next utilisée par {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Erreur /next: {e}", exc_info=True)
        await update.message.reply_text("❌ Erreur lors de la récupération des prochains animes.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /help — liste les commandes disponibles."""
    text = (
        "🤖 <b>Bot Anime VF — Commandes disponibles</b>\n\n"
        "/stats — Statistiques du bot (animes publiés, prochain cycle…)\n"
        "/next — Voir les prochains animes en attente de publication\n"
        "/forcecycle — Déclencher un cycle de publication immédiatement\n"
        "/help — Afficher cette aide\n\n"
        "<i>Le bot publie automatiquement les nouveaux animes VF toutes les "
        f"{CHECK_INTERVAL_MINUTES} minutes.</i>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
