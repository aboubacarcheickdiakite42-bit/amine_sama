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
from state_forwarder import get_forwarded_count, is_paused, set_paused, get_paused_since, get_published_filenames_count

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
        "<b>⚙️ Contrôle :</b>\n"
        "/pause — Mettre le bot en pause\n"
        "/reprendre — Relancer le bot\n\n"
        "<b>📊 Autre :</b>\n"
        "/scan @canal 200 — Re-scanner l'historique\n"
        "/doublons — Voir l'index anti-doublon\n"
        "/stats — Statistiques complètes\n"
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
    total_filenames = get_published_filenames_count()
    keywords = load_keywords()
    paused = is_paused()
    uptime = datetime.now() - _bot_start_time
    uptime_str = f"{int(uptime.total_seconds() // 3600)}h {int((uptime.total_seconds() % 3600) // 60)}min"

    status = "⏸️ En pause" if paused else "🟢 Actif"
    lines = [
        "📊 <b>Statistiques du Bot</b>",
        "",
        f"État : {status}",
        f"⏱️ <b>En ligne depuis :</b> {uptime_str}",
        "",
        f"📡 <b>Canaux surveillés :</b> {len(channels)}",
        f"📺 <b>Vidéos transférées :</b> {total_forwarded}",
        f"🔒 <b>Doublons bloqués (index) :</b> {total_filenames} fichiers indexés",
        f"🔍 <b>Filtre actif :</b> {', '.join(keywords) if keywords else 'aucun'}",
    ]

    if channels:
        lines.append("")
        lines.append("<b>Canaux sources :</b>")
        for ch in channels:
            lines.append(f"  • {ch}")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_doublons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /doublons — affiche les stats anti-doublon et permet de ré-indexer."""
    from state_forwarder import get_published_filenames_count, load_forward_state

    total = get_published_filenames_count()

    if context.args and context.args[0].lower() == "reindex":
        await update.message.reply_text(
            "🔄 Ré-indexation du canal en cours...",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(_do_reindex(update))
        return

    state = load_forward_state()
    filenames = state.get("filenames", {})

    # Afficher les 10 derniers fichiers indexés
    recent = sorted(filenames.items(), key=lambda x: x[1], reverse=True)[:10]

    lines = [
        "🔒 <b>Protection anti-doublon</b>",
        "",
        f"Fichiers indexés : <b>{total}</b>",
        "",
        "Les vidéos avec un nom déjà connu sont automatiquement ignorées,",
        "même si elles viennent d'un canal source différent.",
        "",
    ]

    if recent:
        lines.append("<b>10 derniers fichiers indexés :</b>")
        for fname, date in recent:
            date_str = date[:10]
            lines.append(f"  • <code>{fname[:50]}</code> ({date_str})")
        lines.append("")

    lines.append("Pour ré-indexer l'historique du canal : /doublons reindex")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def _do_reindex(update):
    """Ré-indexe le canal cible en arrière-plan."""
    from forwarder import index_target_channel, SESSION_FILE
    from config import get_telethon_credentials
    from telethon import TelegramClient

    API_ID, API_HASH, PHONE = get_telethon_credentials()
    try:
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        await client.start(phone=PHONE)
        count = await index_target_channel(client, limit=500)
        await client.disconnect()
        total = get_published_filenames_count()
        await update.message.reply_text(
            f"✅ Ré-indexation terminée !\n{count} vidéos scannées\n{total} fichiers dans l'index",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur ré-indexation : {e}")


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
    """
    /scan — scanner tous les canaux configurés (100 derniers messages)
    /scan @canal — scanner un canal spécifique
    /scan @canal 200 — scanner avec une limite personnalisée
    /scan @canal1 @canal2 300 — scanner plusieurs canaux avec limite
    """
    channels = load_channels()
    args = list(context.args) if context.args else []

    # Extraire la limite si le dernier argument est un nombre
    limit = 100
    if args and args[-1].isdigit():
        limit = max(10, min(int(args[-1]), 500))  # entre 10 et 500
        args = args[:-1]

    if not args:
        if not channels:
            await update.message.reply_text("❌ Aucun canal configuré. Ajoutez-en avec /addcanal @nom")
            return
        targets = channels
    else:
        targets = []
        for arg in args:
            ch = arg.strip().lstrip("@")
            targets.append(f"@{ch}")

    await update.message.reply_text(
        f"🔄 Scan de <b>{len(targets)} canal(aux)</b> — {limit} derniers messages par canal...\n"
        f"Je vous préviens quand c'est terminé.",
        parse_mode=ParseMode.HTML
    )

    asyncio.create_task(_do_scan(update, targets, limit))


async def _do_scan(update, targets: list[str], limit: int = 100):
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
            count = await scan_and_forward_history(client, ch, limit=limit)
            results.append(f"• {ch} → {count} vidéo(s)")
            total += count

        await client.disconnect()

        lines = [
            f"✅ <b>Scan terminé !</b>",
            f"Limite : {limit} messages/canal",
            "",
            f"Total : <b>{total} vidéo(s)</b> transférée(s)",
            "",
        ]
        lines.extend(results)
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    except Exception as e:
        await update.message.reply_text(f"❌ Erreur lors du scan : {e}")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /pause — met le bot en pause."""
    if is_paused():
        await update.message.reply_text(
            "⏸️ Le bot est <b>déjà en pause</b>.\nUtilise /reprendre pour relancer.",
            parse_mode=ParseMode.HTML
        )
        return
    set_paused(True)
    await update.message.reply_text(
        "⏸️ <b>Bot mis en pause.</b>\n\n"
        "Les nouveaux messages ne seront plus transférés.\n"
        "Utilise /reprendre pour relancer.",
        parse_mode=ParseMode.HTML
    )
    logger.info(f"Bot mis en pause par {update.effective_user.id}")


async def cmd_reprendre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /reprendre — relance le bot après une pause."""
    if not is_paused():
        await update.message.reply_text(
            "▶️ Le bot est <b>déjà actif</b>, rien à faire.",
            parse_mode=ParseMode.HTML
        )
        return
    paused_since = get_paused_since()
    set_paused(False)
    msg = "▶️ <b>Bot relancé !</b>\n\nLes vidéos seront à nouveau transférées automatiquement."
    if paused_since:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(paused_since)
            msg += f"\n\n<i>En pause depuis : {dt.strftime('%d/%m/%Y %H:%M')}</i>"
        except Exception:
            pass
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    logger.info(f"Bot relancé par {update.effective_user.id}")


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
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("reprendre", cmd_reprendre))
    app.add_handler(CommandHandler("doublons", cmd_doublons))
    return app
