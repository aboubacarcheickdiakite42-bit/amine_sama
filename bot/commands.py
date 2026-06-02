"""
Gestionnaire des commandes Telegram du bot.
"""

import logging
import os
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from state import get_published_count, get_total_episodes_published, get_all_anime_states
from scraper import get_seasonal_animes, get_next_episode_to_publish

logger = logging.getLogger(__name__)

CHANNEL_ID = os.environ["TELEGRAM_CHANNEL_ID"]
CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "60"))
EPISODES_PER_CYCLE = int(os.environ.get("ANIMES_PER_CYCLE", "3"))

_scheduler_ref = None
_bot_start_time = datetime.now()


def set_scheduler(scheduler):
    global _scheduler_ref
    _scheduler_ref = scheduler


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /stats — affiche les statistiques du bot."""
    try:
        anime_states = get_all_anime_states()
        total_animes = len(anime_states)
        total_eps = get_total_episodes_published()

        # Dernier épisode publié
        last_entry = None
        last_time = None
        if anime_states:
            latest = max(anime_states.items(), key=lambda x: x[1].get("updated_at", ""))
            last_entry = latest[1]
            try:
                last_time = datetime.fromisoformat(latest[1].get("updated_at", ""))
            except Exception:
                pass

        # Prochain cycle
        next_run = None
        if _scheduler_ref:
            job = _scheduler_ref.get_job("anime_vf_cycle")
            if job and job.next_run_time:
                next_run = job.next_run_time.replace(tzinfo=None)

        # Uptime
        uptime = datetime.now() - _bot_start_time
        uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}min"

        lines = [
            "📊 <b>Statistiques du Bot Anime VF</b>",
            "",
            f"🎌 <b>Animes suivis :</b> {total_animes}",
            f"📺 <b>Épisodes publiés :</b> {total_eps}",
        ]

        if last_entry:
            lines.append("")
            lines.append(f"🕐 <b>Dernier publié :</b> {last_entry.get('title', '?')} — EP{last_entry.get('last_episode', '?')}")
            if last_time:
                lines.append(f"   <i>{last_time.strftime('%d/%m/%Y à %H:%M')}</i>")

        # Résumé des animes en cours
        if anime_states:
            lines.append("")
            lines.append("<b>Progression par anime :</b>")
            for data in list(anime_states.values())[:5]:
                t = data.get("title", "?")
                ep = data.get("last_episode", 0)
                lines.append(f"  • {t[:30]} → EP{ep}")
            if total_animes > 5:
                lines.append(f"  <i>... et {total_animes - 5} autre(s)</i>")

        lines.append("")
        lines.append(f"⏱️ <b>Intervalle :</b> {CHECK_INTERVAL_MINUTES} min | <b>Par cycle :</b> {EPISODES_PER_CYCLE} eps")

        if next_run:
            diff = next_run - datetime.now()
            mins = max(0, int(diff.total_seconds() // 60))
            lines.append(f"⏰ <b>Prochain cycle dans :</b> {mins} minute(s)")

        lines.append(f"🟢 <b>En ligne depuis :</b> {uptime_str}")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        logger.info(f"Commande /stats utilisée par {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Erreur /stats: {e}", exc_info=True)
        await update.message.reply_text("❌ Erreur lors de la récupération des statistiques.")


async def cmd_forcecycle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /forcecycle — déclenche un cycle immédiat."""
    try:
        await update.message.reply_text("⚙️ Lancement d'un cycle immédiat...")

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
    """Commande /next — affiche les prochains épisodes à publier."""
    try:
        await update.message.reply_text("🔍 Recherche des prochains épisodes disponibles...")

        from state import get_last_published_episode
        animes = get_seasonal_animes(limit=20)

        pending = []
        for anime in animes:
            mal_id = anime["mal_id"]
            last_ep = get_last_published_episode(mal_id)
            episode = get_next_episode_to_publish(mal_id, last_ep)
            if episode:
                pending.append((anime, episode, last_ep))

        if not pending:
            await update.message.reply_text("✅ Aucun nouvel épisode disponible pour le moment.")
            return

        lines = [f"🎌 <b>{len(pending)} épisode(s) prêt(s) à publier :</b>", ""]
        for anime, episode, last_ep in pending[:8]:
            ep_num = episode["episode_num"]
            status = "🆕 Nouveau" if last_ep == 0 else f"Suite (EP{last_ep} → EP{ep_num})"
            lines.append(f"• <b>{anime['title'][:30]}</b> — EP{ep_num} <i>({status})</i>")

        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        logger.info(f"Commande /next utilisée par {update.effective_user.id}")

    except Exception as e:
        logger.error(f"Erreur /next: {e}", exc_info=True)
        await update.message.reply_text("❌ Erreur lors de la recherche des épisodes.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /help — liste les commandes disponibles."""
    text = (
        "🤖 <b>Bot Anime VF — Commandes disponibles</b>\n\n"
        "/stats — Progression par anime, épisodes publiés, prochain cycle\n"
        "/next — Voir les prochains épisodes prêts à être publiés\n"
        "/forcecycle — Déclencher une publication immédiatement\n"
        "/help — Afficher cette aide\n\n"
        "<i>Le bot publie automatiquement les épisodes VF toutes les "
        f"{CHECK_INTERVAL_MINUTES} minutes, épisode par épisode en commençant par EP1.</i>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
