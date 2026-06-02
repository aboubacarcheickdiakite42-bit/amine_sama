"""
Script d'authentification Telethon — à exécuter UNE SEULE FOIS.
Crée le fichier de session userbot_session.session qui permet
au bot de se connecter sans redemander de code à chaque démarrage.
"""

import os
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE = os.environ["TELEGRAM_PHONE"]

SESSION_FILE = os.path.join(os.path.dirname(__file__), "userbot_session")


async def authenticate():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"\n✅ Déjà connecté en tant que: {me.first_name} (@{me.username})")
        print("La session est valide. Vous pouvez démarrer le bot principal.")
        await client.disconnect()
        return

    print(f"\n📱 Envoi du code de vérification au {PHONE}...")
    await client.send_code_request(PHONE)

    code = input("📲 Entrez le code reçu sur Telegram: ").strip()

    try:
        await client.sign_in(PHONE, code)
    except SessionPasswordNeededError:
        password = input("🔒 Entrez votre mot de passe 2FA Telegram: ").strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"\n✅ Connecté avec succès en tant que: {me.first_name} (@{me.username})")
    print("Session sauvegardée. Vous pouvez maintenant démarrer le bot principal.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(authenticate())
