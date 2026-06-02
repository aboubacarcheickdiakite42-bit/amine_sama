"""
Authentification Telethon via interface web.
Lance un serveur HTTP simple pour recevoir le code de vérification.
"""

import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from config import get_telethon_credentials
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_ID, API_HASH, PHONE = get_telethon_credentials()
SESSION_FILE = os.path.join(os.path.dirname(__file__), "userbot_session")
PORT = int(os.environ.get("PORT", 3000))

# État partagé entre le serveur HTTP et le client Telethon
state = {
    "step": "start",       # start → waiting_code → waiting_password → done → error
    "code_hash": None,
    "client": None,
    "message": "",
    "code_received": None,
    "password_received": None,
}
code_event = asyncio.Event()
password_event = asyncio.Event()
loop = None


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Authentification Telegram Bot</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 480px; margin: 60px auto; padding: 20px; background: #f0f2f5; }}
  .card {{ background: white; border-radius: 12px; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }}
  h1 {{ color: #1a1a2e; font-size: 1.4em; margin-bottom: 8px; }}
  p {{ color: #555; margin-bottom: 20px; }}
  input {{ width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 1.1em; box-sizing: border-box; text-align: center; letter-spacing: 4px; }}
  button {{ width: 100%; padding: 14px; background: #2196F3; color: white; border: none; border-radius: 8px; font-size: 1em; cursor: pointer; margin-top: 12px; }}
  button:hover {{ background: #1976D2; }}
  .success {{ color: #4CAF50; font-weight: bold; }}
  .error {{ color: #f44336; font-weight: bold; }}
  .status {{ padding: 12px; border-radius: 8px; margin-top: 16px; text-align: center; }}
  .status.ok {{ background: #e8f5e9; color: #2e7d32; }}
  .status.err {{ background: #ffebee; color: #c62828; }}
</style>
</head>
<body>
<div class="card">
  <h1>🤖 Authentification Telegram</h1>
  {content}
</div>
</body>
</html>"""


def render_waiting_code():
    return HTML_TEMPLATE.format(content=f"""
  <p>Un code de vérification a été envoyé sur <strong>{PHONE}</strong> via Telegram.</p>
  <form method="POST" action="/submit_code">
    <input type="text" name="code" placeholder="12345" maxlength="10" autofocus required />
    <button type="submit">✅ Valider le code</button>
  </form>
""")


def render_waiting_password():
    return HTML_TEMPLATE.format(content="""
  <p>Votre compte a la <strong>vérification en 2 étapes</strong> activée. Entrez votre mot de passe Telegram.</p>
  <form method="POST" action="/submit_password">
    <input type="password" name="password" placeholder="Mot de passe" autofocus required style="letter-spacing:normal;" />
    <button type="submit">🔒 Valider</button>
  </form>
""")


def render_done():
    return HTML_TEMPLATE.format(content="""
  <div class="status ok">
    ✅ <strong>Connexion réussie !</strong><br><br>
    La session est sauvegardée. Vous pouvez fermer cette page.<br><br>
    Le bot principal va démarrer automatiquement.
  </div>
""")


def render_error(msg):
    return HTML_TEMPLATE.format(content=f"""
  <div class="status err">
    ❌ <strong>Erreur :</strong> {msg}<br><br>
    Rechargez la page pour réessayer.
  </div>
""")


def render_start():
    return HTML_TEMPLATE.format(content="""
  <p>Initialisation en cours... Veuillez patienter quelques secondes puis recharger la page.</p>
  <script>setTimeout(() => location.reload(), 3000);</script>
""")


class AuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silencer les logs HTTP

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        step = state["step"]
        if step == "waiting_code":
            self.wfile.write(render_waiting_code().encode())
        elif step == "waiting_password":
            self.wfile.write(render_waiting_password().encode())
        elif step == "done":
            self.wfile.write(render_done().encode())
        elif step == "error":
            self.wfile.write(render_error(state["message"]).encode())
        else:
            self.wfile.write(render_start().encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        params = parse_qs(body)

        if self.path == "/submit_code":
            code = params.get("code", [""])[0].strip()
            if code:
                state["code_received"] = code
                asyncio.run_coroutine_threadsafe(set_code_event(), loop)

        elif self.path == "/submit_password":
            password = params.get("password", [""])[0].strip()
            if password:
                state["password_received"] = password
                asyncio.run_coroutine_threadsafe(set_password_event(), loop)

        # Rediriger vers la page principale
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


async def set_code_event():
    code_event.set()


async def set_password_event():
    password_event.set()


async def authenticate():
    global loop
    loop = asyncio.get_running_loop()

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    state["client"] = client

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        state["step"] = "done"
        logger.info(f"✅ Déjà connecté en tant que: {me.first_name} (@{me.username})")
        await client.disconnect()
        return True

    logger.info(f"📱 Envoi du code au {PHONE}...")
    result = await client.send_code_request(PHONE)
    state["code_hash"] = result.phone_code_hash
    state["step"] = "waiting_code"
    logger.info("⏳ En attente du code de vérification via l'interface web...")

    # Attendre le code
    await code_event.wait()
    code = state["code_received"]
    state["step"] = "processing"
    logger.info(f"📲 Code reçu, tentative de connexion...")

    try:
        await client.sign_in(PHONE, code, phone_code_hash=state["code_hash"])
    except SessionPasswordNeededError:
        state["step"] = "waiting_password"
        logger.info("🔒 2FA requis — en attente du mot de passe...")
        await password_event.wait()
        password = state["password_received"]
        await client.sign_in(password=password)

    me = await client.get_me()
    state["step"] = "done"
    logger.info(f"✅ Connecté : {me.first_name} (@{me.username})")
    await client.disconnect()
    return True


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), AuthHandler)
    logger.info(f"🌐 Interface d'authentification sur le port {PORT}")
    server.serve_forever()


async def main():
    logger.info(f"API_ID: {API_ID} | HASH longueur: {len(API_HASH)} | PHONE: {PHONE}")

    # Lancer le serveur HTTP dans un thread
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    try:
        success = await authenticate()
        if success:
            logger.info("🎉 Authentification terminée ! Vous pouvez fermer cette page.")
            # Garder le serveur actif pour afficher la page de succès
            await asyncio.sleep(30)
    except Exception as e:
        state["step"] = "error"
        state["message"] = str(e)
        logger.error(f"❌ Erreur authentification: {e}", exc_info=True)
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
