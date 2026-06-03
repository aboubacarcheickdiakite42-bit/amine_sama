"""
Utilitaires pour détecter et grouper les séries anime depuis les noms de fichiers.
"""

import re
import logging
import aiohttp

logger = logging.getLogger(__name__)

# Patterns de noms de fichiers anime courants
# Ex: "Naruto S01 EP01 VF.mp4"
# Ex: "[Canal] Dragon Ball Z S02 EP15 VOSTFR Convertie.mkv"
# Ex: "One Piece EP1001 French.mp4"
_RE_SERIES = re.compile(
    r"""
    (?:\[.*?\]\s*)?                        # [tag canal] optionnel
    (?P<title>.+?)                         # Titre de la série
    \s+
    (?:S(?P<season>\d{1,2})\s*)?           # Saison optionnelle (S01, S2...)
    EP?(?P<episode>\d{1,4})               # Épisode (EP01, EP1, E01...)
    (?:\s+.*)?$                            # Reste (VF, VOSTFR, Convertie...)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Mots-clés VOSTFR/VOSTA à toujours rejeter
VOSTFR_KEYWORDS = ["vostfr", "vosta", "vost", "sous-titre", "subtitles", "sub"]

# Mots-clés VF à accepter (si filtre VF actif)
VF_KEYWORDS = ["vf", "french", "vf ", " vf", "francais", "français", "dubbed", "dub"]


def is_vostfr(text: str) -> bool:
    """Retourne True si le texte indique un contenu VOSTFR (à rejeter)."""
    t = text.lower()
    # Détecter VOSTFR explicitement
    for kw in VOSTFR_KEYWORDS:
        if kw in t:
            return True
    return False


def is_vf(text: str) -> bool:
    """Retourne True si le texte indique un contenu VF."""
    t = text.lower()
    for kw in VF_KEYWORDS:
        if kw in t:
            return True
    return False


def parse_series_info(filename: str) -> dict | None:
    """
    Extrait les informations de série depuis un nom de fichier.
    Retourne un dict avec 'title', 'season', 'episode' ou None si non reconnu.
    """
    # Nettoyer l'extension
    name = re.sub(r'\.(mp4|mkv|avi|mov|webm)$', '', filename, flags=re.IGNORECASE).strip()

    m = _RE_SERIES.match(name)
    if not m:
        return None

    title = m.group("title").strip()
    # Nettoyer le titre : supprimer les tags de canal restants
    title = re.sub(r'^\[.*?\]\s*', '', title).strip()
    # Normaliser les espaces
    title = re.sub(r'\s+', ' ', title)

    season = int(m.group("season")) if m.group("season") else 1
    episode = int(m.group("episode"))

    return {
        "title": title,
        "season": season,
        "episode": episode,
        "series_key": f"{title.lower()}::s{season:02d}",
    }


def group_messages_by_series(messages: list) -> dict[str, list]:
    """
    Groupe les messages vidéo par clé de série (titre + saison).
    Retourne un dict: series_key → liste de (episode_number, message)
    """
    from forwarder import get_filename

    groups: dict[str, list] = {}
    ungrouped = []

    for msg in messages:
        fname = get_filename(msg)
        if not fname:
            continue
        info = parse_series_info(fname)
        if info:
            key = info["series_key"]
            if key not in groups:
                groups[key] = []
            groups[key].append((info["episode"], msg, info))
        else:
            ungrouped.append(msg)

    # Trier chaque groupe par numéro d'épisode
    for key in groups:
        groups[key].sort(key=lambda x: x[0])

    return groups, ungrouped


def is_series_complete(episodes: list) -> bool:
    """
    Vérifie si une série semble complète (EP01 présent, pas de trous majeurs).
    On considère une série complète si elle commence à EP01 et n'a pas de trou > 2.
    """
    if not episodes:
        return False
    ep_numbers = sorted([e[0] for e in episodes])
    # Doit commencer à EP01
    if ep_numbers[0] != 1:
        return False
    # Pas de trous > 2 entre épisodes consécutifs
    for i in range(1, len(ep_numbers)):
        if ep_numbers[i] - ep_numbers[i - 1] > 2:
            return False
    return True


def get_series_title_clean(info: dict) -> str:
    """Retourne un titre propre pour affichage."""
    title = info["title"]
    season = info["season"]
    if season > 1:
        return f"{title} — Saison {season}"
    return title


async def fetch_anime_cover(title: str) -> str | None:
    """
    Tente de récupérer une image de couverture depuis l'API Jikan (MyAnimeList).
    Retourne l'URL de l'image ou None si introuvable.
    """
    try:
        # Nettoyer le titre pour la recherche
        search_title = re.sub(r'\s+S\d+$', '', title, flags=re.IGNORECASE).strip()
        url = f"https://api.jikan.moe/v4/anime?q={search_title}&limit=1&type=tv"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("data", [])
                    if results:
                        image_url = results[0].get("images", {}).get("jpg", {}).get("large_image_url")
                        if image_url:
                            logger.info(f"🖼️ Couverture trouvée pour '{title}': {image_url}")
                            return image_url
    except Exception as e:
        logger.warning(f"⚠️ Impossible de récupérer couverture pour '{title}': {e}")
    return None
