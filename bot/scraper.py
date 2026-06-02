"""
Scraper pour trouver les animes disponibles en VF.
Utilise plusieurs sources pour maximiser la couverture.
"""

import requests
from bs4 import BeautifulSoup
import logging
import json
import re
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


def scrape_neko_sama() -> list[dict]:
    """Scrape neko-sama.fr pour les derniers animes VF ajoutés."""
    animes = []
    try:
        url = "https://www.neko-sama.fr/anime/info/latest"
        resp = SESSION.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        cards = soup.select(".anime-card, .card-anime, article.anime")
        if not cards:
            cards = soup.select("a[href*='/anime/info/']")

        seen = set()
        for card in cards[:20]:
            try:
                link_tag = card if card.name == "a" else card.find("a", href=True)
                if not link_tag:
                    continue
                href = link_tag.get("href", "")
                if "/anime/info/" not in href:
                    continue

                title_tag = card.find(["h3", "h2", "h4", ".title", ".name"])
                title = title_tag.get_text(strip=True) if title_tag else link_tag.get_text(strip=True)
                if not title or title in seen:
                    continue

                img_tag = card.find("img")
                image = img_tag.get("src") or img_tag.get("data-src") if img_tag else None

                full_url = href if href.startswith("http") else f"https://www.neko-sama.fr{href}"

                lang_tag = card.find(string=re.compile(r"VF", re.I))
                if lang_tag is None:
                    badge = card.find(class_=re.compile(r"vf|lang", re.I))
                    if badge is None:
                        continue

                seen.add(title)
                animes.append({
                    "title": title,
                    "url": full_url,
                    "image": image,
                    "source": "neko-sama",
                    "lang": "VF",
                })
            except Exception as e:
                logger.debug(f"Erreur carte neko-sama: {e}")
                continue

    except Exception as e:
        logger.warning(f"Erreur scraping neko-sama: {e}")

    return animes


def scrape_anime_vf_org() -> list[dict]:
    """Scrape animevf.cc pour les dernières sorties VF."""
    animes = []
    try:
        url = "https://animevf.cc/"
        resp = SESSION.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        cards = soup.select(".last_episodes li, .items article, .anime-item, .item")
        seen = set()
        for card in cards[:20]:
            try:
                link_tag = card.find("a", href=True)
                if not link_tag:
                    continue

                title_tag = card.find(["h3", "h2", ".name", ".title"])
                title = title_tag.get_text(strip=True) if title_tag else link_tag.get("title", "")
                if not title or title in seen:
                    continue

                img_tag = card.find("img")
                image = None
                if img_tag:
                    image = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-original")

                href = link_tag["href"]
                full_url = href if href.startswith("http") else f"https://animevf.cc{href}"

                seen.add(title)
                animes.append({
                    "title": title,
                    "url": full_url,
                    "image": image,
                    "source": "animevf",
                    "lang": "VF",
                })
            except Exception as e:
                logger.debug(f"Erreur carte animevf: {e}")
                continue

    except Exception as e:
        logger.warning(f"Erreur scraping animevf: {e}")

    return animes


def scrape_jkanime_vf() -> list[dict]:
    """Scrape une API publique d'animes (Jikan/MAL) pour les nouvelles sorties VF."""
    animes = []
    try:
        url = "https://api.jikan.moe/v4/top/anime?filter=airing&limit=10"
        resp = SESSION.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("data", [])[:10]:
            try:
                title_fr = item.get("title") or item.get("title_english") or ""
                if not title_fr:
                    continue
                animes.append({
                    "title": title_fr,
                    "url": item.get("url", "https://myanimelist.net"),
                    "image": item.get("images", {}).get("jpg", {}).get("large_image_url"),
                    "source": "jikan-mal",
                    "lang": "VF",
                    "synopsis": item.get("synopsis", "")[:300] if item.get("synopsis") else "",
                    "score": item.get("score"),
                    "genres": [g["name"] for g in item.get("genres", [])[:3]],
                    "episodes": item.get("episodes"),
                    "status": item.get("status"),
                    "aired": item.get("aired", {}).get("string", ""),
                })
            except Exception as e:
                logger.debug(f"Erreur item jikan: {e}")
                continue

    except Exception as e:
        logger.warning(f"Erreur scraping jikan: {e}")

    return animes


def get_latest_anime_vf(max_results: int = 5) -> list[dict]:
    """
    Récupère les derniers animes VF disponibles depuis plusieurs sources.
    Retourne une liste dédupliquée.
    """
    all_animes = []

    # Source principale : Jikan/MAL API (fiable et sans blocage)
    jikan_results = scrape_jikan_seasonal()
    all_animes.extend(jikan_results)

    # Sources de scraping secondaires
    if len(all_animes) < max_results:
        all_animes.extend(scrape_neko_sama())

    if len(all_animes) < max_results:
        all_animes.extend(scrape_anime_vf_org())

    # Déduplier par titre
    seen_titles = set()
    unique = []
    for anime in all_animes:
        key = anime["title"].lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            unique.append(anime)

    logger.info(f"Trouvé {len(unique)} animes uniques VF")
    return unique[:max_results]


def scrape_jikan_seasonal() -> list[dict]:
    """Récupère les animes de la saison actuelle via Jikan API."""
    animes = []
    try:
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

        url = f"https://api.jikan.moe/v4/seasons/{year}/{season}?limit=15"
        resp = SESSION.get(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("data", [])[:15]:
            try:
                title = item.get("title") or item.get("title_english") or ""
                if not title:
                    continue

                synopsis = item.get("synopsis", "") or ""
                synopsis_short = synopsis[:280] + "..." if len(synopsis) > 280 else synopsis

                animes.append({
                    "title": title,
                    "title_jp": item.get("title_japanese", ""),
                    "url": item.get("url", "https://myanimelist.net"),
                    "image": item.get("images", {}).get("jpg", {}).get("large_image_url"),
                    "source": "jikan-seasonal",
                    "lang": "VF",
                    "synopsis": synopsis_short,
                    "score": item.get("score"),
                    "genres": [g["name"] for g in item.get("genres", [])[:3]],
                    "episodes": item.get("episodes"),
                    "status": item.get("status"),
                    "studio": item.get("studios", [{}])[0].get("name", "") if item.get("studios") else "",
                    "season": f"{season.capitalize()} {year}",
                    "mal_id": item.get("mal_id"),
                })
            except Exception as e:
                logger.debug(f"Erreur item seasonal: {e}")
                continue

    except Exception as e:
        logger.warning(f"Erreur scraping jikan seasonal: {e}")

    return animes
