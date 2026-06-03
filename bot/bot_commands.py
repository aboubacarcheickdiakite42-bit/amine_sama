"""
Commandes Telegram du bot (via python-telegram-bot).
Permet de gérer les canaux sources depuis Telegram.
"""

import logging
import os
import asyncio
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, Application, CommandHandler
from telegram.constants import ParseMode

from channels_config import load_channels, add_channel, remove_channel, load_keywords, set_keywords, clear_keywords
from state_forwarder import get_forwarded_count

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
_bot_start_time = datetime.now()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 <b>Bot Anime VF — Transfert automatique</b>\n\n"
        "Je surveille vos canaux sources et transfère automatiquement "
        "les vidéos vers votre canal.\n\n"
        "<b>📡 Canaux :</b>\n"
        "/addcanal @nom — Ajouter un canal source\n"
        "/removecanal @nom — Supprimer un canal source\n"
        "/canaux — Voir les canaux surveillés\n\n"
        "<b>🔍 Filtre :</b>\n"
        "/setfiltre vf french — N'envoyer que les vidéos VF\n"
        "/filtre — Voir le filtre actif\n"
        "/clearfiltre — Désactiver le filtre\n\n"
        "<b>📊 Autre :</b>\n"
        "/scan @canal — Re-scanner l'historique d'un canal\n"
        "/stats — Statistiques\n"
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


async def cmd_setfiltre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /setfiltre mot1 mot2 — définit les mots-clés de filtre."""
    if not context.args:
        await update.message.reply_text(
            "❌ Usage: /setfiltre vf french\n\n"
            "Le bot ne transférera que les vidéos dont le nom de fichier ou le texte contient ces mots.\n\n"
            "Exemple: /setfiltre vf french vostfr\n\n"
            "Pour désactiver le filtre (tout transférer): /clearfiltre",
            parse_mode=ParseMode.HTML
        )
        return

    keywords = [kw.lower().strip() for kw in context.args if kw.strip()]
    set_keywords(keywords)

    lines = [
        "✅ <b>Filtre mis à jour !</b>",
        "",
        "Mots-clés actifs :",
    ]
    for kw in keywords:
        lines.append(f"  • <code>{kw}</code>")
    lines.append("")
    lines.append("Seules les vidéos contenant un de ces mots seront transférées.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
    logger.info(f"Filtre mis à jour par {update.effective_user.id}: {keywords}")


async def cmd_filtre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /filtre — affiche les mots-clés de filtre actifs."""
    keywords = load_keywords()
    if not keywords:
        await update.message.reply_text(
            "🔓 <b>Aucun filtre actif</b> — toutes les vidéos sont transférées.\n\n"
            "Pour activer un filtre: /setfiltre vf french",
            parse_mode=ParseMode.HTML
        )
        return

    lines = ["🔍 <b>Filtre actif — mots-clés :</b>", ""]
    for kw in keywords:
        lines.append(f"  • <code>{kw}</code>")
    lines.append("")
    lines.append("Pour modifier: /setfiltre mot1 mot2\nPour désactiver: /clearfiltre")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /scan @canal — force un re-scan complet de l'historique d'un canal."""
    channels = load_channels()

    if not context.args:
        if not channels:
            await update.message.reply_text("❌ Aucun canal configuré. Ajoutez-en avec /addcanal @nom")
            return
        # Scan de tous les canaux configurés
        targets = channels
    else:
        targets = []
        for arg in context.args:
            ch = arg.strip()
            if not ch.startswith("@"):
                ch = "@" + ch
            targets.append(ch)

    await update.message.reply_text(
        f"🔄 Scan en cours de {len(targets)} canal(aux)...\nCela peut prendre plusieurs minutes.",
        parse_mode=ParseMode.HTML
    )

    # Lancer le scan en tâche de fond pour ne pas bloquer
    asyncio.create_task(_do_scan(update, targets))


async def _do_scan(update, targets: list[str]):
    """Effectue le scan en arrière-plan et envoie le résultat."""
    from forwarder import scan_and_forward_history, SESSION_FILE
    from config import get_telethon_credentials
    from telethon import TelegramClient

    API_ID, API_HASH, PHONE = get_telethon_credentials()
    total = 0
    results = []

    try:
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        await client.start(phone=PHONE)

        for ch in targets:
            count = await scan_and_forward_history(client, ch, limit=100)
            results.append(f"• {ch} → {count} vidéo(s) transférée(s)")
            total += count

        await client.disconnect()

        lines = [f"✅ <b>Scan terminé !</b>", "", f"Total : <b>{total} vidéo(s)</b> transférée(s)", ""]
        lines.extend(results)
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur lors du scan : {e}")


async def cmd_clearfiltre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /clearfiltre — désactive tous les filtres."""
    clear_keywords()
    await update.message.reply_text(
        "🔓 Filtre désactivé — toutes les vidéos seront désormais transférées.",
        parse_mode=ParseMode.HTML
    )


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
    app.add_handler(CommandHandler("setfiltre", cmd_setfiltre))
    app.add_handler(CommandHandler("filtre", cmd_filtre))
    app.add_handler(CommandHandler("clearfiltre", cmd_clearfiltre))
    app.add_handler(CommandHandler("scan", cmd_scan))
    return app
