"""
Commandes Telegram du bot (via python-telegram-bot).
Permet de gérer les canaux sources depuis Telegram.
"""

import logging
import os
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, Application, CommandHandler
from telegram.constants import ParseMode

from channels_config import load_channels, add_channel, remove_channel
from state_forwarder import get_forwarded_count

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
_bot_start_time = datetime.now()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 <b>Bot Anime VF — Transfert automatique</b>\n\n"
        "Je surveille vos canaux sources et transfère automatiquement "
        "les vidéos vers votre canal.\n\n"
        "<b>Commandes :</b>\n"
        "/addcanal @nom — Ajouter un canal source\n"
        "/removecanal @nom — Supprimer un canal source\n"
        "/canaux — Voir les canaux surveillés\n"
        "/stats — Statistiques du bot\n"
        "/help — Cette aide"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_addcanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ajouter un ou plusieurs canaux sources."""
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /addcanal @nomcanal\n\nVous pouvez aussi envoyer plusieurs canaux :\n/addcanal @canal1 @canal2",
            parse_mode=ParseMode.HTML
        )
        return

    added = []
    already = []
    for arg in context.args:
        ch = arg.strip()
        # Accepte aussi les liens t.me/
        if "t.me/" in ch:
            ch = "@" + ch.split("t.me/")[-1].rstrip("/")
        if not ch.startswith("@"):
            ch = "@" + ch
        if add_channel(ch):
            added.append(ch)
        else:
            already.append(ch)

    lines = []
    if added:
        lines.append(f"✅ Canal(aux) ajouté(s) : {', '.join(added)}")
        lines.append("Le bot va maintenant surveiller ce(s) canal(aux) et transférer automatiquement les vidéos.")
    if already:
        lines.append(f"ℹ️ Déjà présent(s) : {', '.join(already)}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    logger.info(f"Canaux ajoutés par {update.effective_user.id}: {added}")


async def cmd_removecanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Supprimer un canal source."""
    if not context.args:
        await update.message.reply_text("❌ Usage: /removecanal @nomcanal")
        return

    removed = []
    not_found = []
    for arg in context.args:
        ch = arg.strip()
        if not ch.startswith("@"):
            ch = "@" + ch
        if remove_channel(ch):
            removed.append(ch)
        else:
            not_found.append(ch)

    lines = []
    if removed:
        lines.append(f"✅ Supprimé(s) : {', '.join(removed)}")
    if not_found:
        lines.append(f"❌ Introuvable(s) : {', '.join(not_found)}")

    await update.message.reply_text("\n".join(lines))


async def cmd_canaux(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche les canaux sources configurés."""
    channels = load_channels()
    if not channels:
        await update.message.reply_text(
            "📭 Aucun canal source configuré.\n\nUtilisez /addcanal @nomcanal pour en ajouter un.",
            parse_mode=ParseMode.HTML
        )
        return

    lines = [f"📡 <b>{len(channels)} canal(aux) surveillé(s) :</b>", ""]
    for ch in channels:
        lines.append(f"• {ch}")
    lines.append("")
    lines.append("Pour supprimer un canal : /removecanal @nomcanal")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Statistiques du bot."""
    channels = load_channels()
    total_forwarded = get_forwarded_count()
    uptime = datetime.now() - _bot_start_time
    uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}min"

    lines = [
        "📊 <b>Statistiques du Bot</b>",
        "",
        f"📡 <b>Canaux surveillés :</b> {len(channels)}",
        f"📺 <b>Vidéos transférées :</b> {total_forwarded}",
        f"🟢 <b>En ligne depuis :</b> {uptime_str}",
    ]

    if channels:
        lines.append("")
        lines.append("<b>Canaux sources :</b>")
        for ch in channels:
            lines.append(f"  • {ch}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


def create_bot_app() -> Application:
    """Crée l'application bot avec toutes les commandes."""
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("addcanal", cmd_addcanal))
    app.add_handler(CommandHandler("removecanal", cmd_removecanal))
    app.add_handler(CommandHandler("canaux", cmd_canaux))
    app.add_handler(CommandHandler("stats", cmd_stats))
    return app
