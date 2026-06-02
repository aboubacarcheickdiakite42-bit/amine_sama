"""
Scraper pour récupérer les animes de la saison et leurs épisodes.
Utilise l'API Jikan (MyAnimeList) comme source principale.
"""

import requests
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Délai entre les appels Jikan pour respecter le rate limit (3 req/s)
JIKAN_DELAY = 0.4


def _jikan_get(url: str, retries: int = 3) -> dict | None:
    """Effectue un GET vers l'API Jikan avec retry et respect du rate limit."""
    for attempt in range(1, retries + 1):
        try:
            time.sleep(JIKAN_DELAY)
            resp = SESSION.get(url, timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 2))
                logger.warning(f"Rate limit Jikan — attente {wait}s")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Erreur Jikan (tentative {attempt}/{retries}) — {url}: {e}")
            if attempt < retries:
                time.sleep(2)
    return None


def get_current_season() -> tuple[int, str]:
    """Retourne l'année et la saison actuelle."""
    now = datetime.now()
    year = now.year
    month = now.month
    if month in [1, 2, 3]:
        season = "winter"
    elif month in [4, 5, 6]:
        season = "spring"
    elif month in [7, 8, 9]:
        season = "summer"
    else:
        season = "fall"
    return year, season


def get_seasonal_animes(limit: int = 20) -> list[dict]:
    """
    Récupère les animes de la saison actuelle via Jikan.
    Retourne une liste d'animes avec leurs métadonnées.
    """
    year, season = get_current_season()
    url = f"https://api.jikan.moe/v4/seasons/{year}/{season}?limit={limit}"
    data = _jikan_get(url)

    if not data:
        logger.error("Impossible de récupérer les animes saisonniers")
        return []

    animes = []
    for item in data.get("data", []):
        try:
            mal_id = item.get("mal_id")
            title = item.get("title") or item.get("title_english") or ""
            if not mal_id or not title:
                continue

            synopsis = item.get("synopsis") or ""
            synopsis_short = synopsis[:280] + "..." if len(synopsis) > 280 else synopsis

            animes.append({
                "mal_id": mal_id,
                "title": title,
                "title_jp": item.get("title_japanese", ""),
                "url": item.get("url", f"https://myanimelist.net/anime/{mal_id}"),
                "image": item.get("images", {}).get("jpg", {}).get("large_image_url"),
                "synopsis": synopsis_short,
                "score": item.get("score"),
                "genres": [g["name"] for g in item.get("genres", [])[:3]],
                "total_episodes": item.get("episodes"),
                "status": item.get("status", ""),
                "studio": item.get("studios", [{}])[0].get("name", "") if item.get("studios") else "",
                "season": f"{season.capitalize()} {year}",
                "lang": "VF",
            })
        except Exception as e:
            logger.debug(f"Erreur item saisonnier: {e}")
            continue

    logger.info(f"Saison {season} {year} : {len(animes)} animes récupérés")
    return animes


def get_anime_episodes(mal_id: int) -> list[dict]:
    """
    Récupère la liste des épisodes d'un anime via Jikan.
    Retourne uniquement les épisodes déjà diffusés (aired).
    """
    url = f"https://api.jikan.moe/v4/anime/{mal_id}/episodes?page=1"
    data = _jikan_get(url)

    if not data:
        return []

    episodes = []
    for ep in data.get("data", []):
        try:
            ep_num = ep.get("mal_id")  # Jikan utilise mal_id pour le numéro d'épisode
            if not ep_num:
                continue

            # Vérifier si l'épisode a été diffusé
            aired_str = ep.get("aired")
            if aired_str:
                try:
                    aired_dt = datetime.fromisoformat(aired_str.replace("Z", "+00:00"))
                    if aired_dt.replace(tzinfo=None) > datetime.now():
                        continue  # Épisode pas encore diffusé
                except Exception:
                    pass  # Si on ne peut pas parser la date, on suppose qu'il est disponible

            ep_title = ep.get("title") or ep.get("title_romanji") or f"Épisode {ep_num}"

            episodes.append({
                "episode_num": ep_num,
                "title": ep_title,
                "title_jp": ep.get("title_japanese", ""),
                "aired": aired_str,
                "filler": ep.get("filler", False),
                "recap": ep.get("recap", False),
            })
        except Exception as e:
            logger.debug(f"Erreur épisode {ep}: {e}")
            continue

    return sorted(episodes, key=lambda x: x["episode_num"])


def get_next_episode_to_publish(mal_id: int, last_published: int) -> dict | None:
    """
    Retourne le prochain épisode à publier pour un anime donné.
    Si last_published=0, retourne l'épisode 1.
    Retourne None si aucun nouvel épisode n'est disponible.
    """
    episodes = get_anime_episodes(mal_id)
    if not episodes:
        return None

    target_ep = last_published + 1
    for ep in episodes:
        if ep["episode_num"] == target_ep:
            return ep

    # Si on ne trouve pas exactement le numéro, chercher le premier supérieur à last_published
    for ep in episodes:
        if ep["episode_num"] > last_published:
            return ep

    return None
