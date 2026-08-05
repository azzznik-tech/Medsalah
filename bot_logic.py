# © 2026 med asava - All rights reserved
"""
مكتبة البحث عن الأفلام/المسلسلات وترجماتها — تعمل بشكل مستقل تماماً
بدون أي حاجة للتليجرام. تستخدم مباشرة من واجهة التطبيق (main.py).
"""

import io
import logging
import os
import re
import zipfile

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# المفاتيح
# ═══════════════════════════════════════════════════════

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "267b5b6916bb1e7f59f613ed78f54c12")
TMDB_API_KEY_2 = os.environ.get("TMDB_API_KEY_2", "53aebbda42312a223dae9560881c3905")
SUBSOURCE_API_KEY = os.environ.get(
    "SUBSOURCE_API_KEY",
    "sk_672398fa8bdd191d48e598c408d786a6afa061e336236fc5c40b332678f67100"
)
SUBSOURCE_API_KEY_2 = os.environ.get(
    "SUBSOURCE_API_KEY_2",
    "sk_ea2e48cfd708dc9937a770ed36f654fc3bc4d3f019822f761e87293736e6c7ec"
)

TMDB_BASE = "https://api.themoviedb.org/3"
SUBSOURCE_BASE = "https://api.subsource.net/api/v1"

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

# ═══════════════════════════════════════════════════════
# TMDB
# ═══════════════════════════════════════════════════════


def _tmdb_placeholder(key: str) -> bool:
    return not key


def tmdb_search(query: str):
    """يبحث بمفتاح TMDB الأول، ويجرب الثاني تلقائياً إذا فشل الأول."""
    url = f"{TMDB_BASE}/search/multi"
    keys_to_try = [k for k in (TMDB_API_KEY, TMDB_API_KEY_2) if not _tmdb_placeholder(k)]

    last_error = None
    for key in keys_to_try:
        params = {
            "api_key": key,
            "query": query,
            "language": "ar",
            "include_adult": "false",
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return [r for r in results if r.get("media_type") in ("movie", "tv")]
        except Exception as e:
            last_error = e
            logger.error(f"TMDB key failed, trying next if available: {e}")
            continue
    if last_error:
        raise last_error
    return []


def format_movie_info(item: dict) -> str:
    """يرجّع نصاً منسّقاً فيه العنوان والسنة والنوع والتقييم والوصف."""
    title = item.get("title") or item.get("name") or "غير معروف"
    original = item.get("original_title") or item.get("original_name") or ""
    date = item.get("release_date") or item.get("first_air_date") or ""
    year = date.split("-")[0] if date else "غير معروف"
    media_type = "فيلم" if item.get("media_type") == "movie" else "مسلسل"
    overview = item.get("overview") or "لا يوجد وصف متاح."
    rating = item.get("vote_average", 0)
    text = (
        f"{title}" + (f" ({original})" if original and original != title else "") +
        "\n"
        f"السنة: {year}\n"
        f"النوع: {media_type}\n"
        f"التقييم: {rating}/10\n\n"
        f"{overview}"
    )
    return text


def extract_year(item: dict):
    date = item.get("release_date") or item.get("first_air_date")
    if date and date.split("-")[0].isdigit():
        return int(date.split("-")[0])
    return None


# ═══════════════════════════════════════════════════════
# SubSource
# ═══════════════════════════════════════════════════════


class SubSourceAuthError(Exception):
    pass


def _subsource_placeholder(key: str) -> bool:
    return not key


def _subsource_keys():
    return [k for k in (SUBSOURCE_API_KEY, SUBSOURCE_API_KEY_2) if not _subsource_placeholder(k)]


def _subsource_headers(key: str):
    return {
        "X-API-Key": key,
        "Accept": "application/json",
        "User-Agent": "MovieSubsApp/1.0",
    }


def _subsource_unwrap(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data") or data.get("items") or data.get("results") or []
    return []


def _subsource_request(method: str, url: str, **kwargs):
    """يجرب مفتاح SubSource الأول، ويجرب الثاني إذا رجع 401."""
    timeout = kwargs.pop("timeout", 15)
    keys = _subsource_keys()
    if not keys:
        raise SubSourceAuthError("لم يتم تعيين أي مفتاح SubSource")

    last_auth_error = None
    for key in keys:
        resp = requests.request(
            method, url, headers=_subsource_headers(key),
            timeout=timeout, **kwargs
        )
        if resp.status_code == 401:
            last_auth_error = SubSourceAuthError("مفتاح SubSource API غير صالح")
            logger.error("SubSource key failed (401), trying next if available")
            continue
        resp.raise_for_status()
        return resp
    raise last_auth_error


def subsource_search(query: str, year: int = None):
    params = {"q": query, "searchType": "text"}
    if year:
        params["year"] = year
    resp = _subsource_request("GET", f"{SUBSOURCE_BASE}/movies/search", params=params)
    return _subsource_unwrap(resp.json())


def subsource_get_subtitles(movie_id, language: str = "arabic"):
    params = {"movieId": movie_id, "language": language}
    resp = _subsource_request("GET", f"{SUBSOURCE_BASE}/subtitles", params=params)
    return _subsource_unwrap(resp.json())


def subsource_download(subtitle_id: int) -> bytes:
    resp = _subsource_request(
        "GET", f"{SUBSOURCE_BASE}/subtitles/{subtitle_id}/download", timeout=30
    )
    return resp.content


def extract_srt(zip_bytes: bytes, fallback_name: str = "subtitle"):
    """يستخرج SRT من ZIP، أو يعيد البيانات كما هي إذا لم تكن ZIP."""
    if zip_bytes[:4] == b"PK\x03\x04":
        try:
            zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
            srt_files = [
                n for n in zf.namelist()
                if n.lower().endswith(".srt") and not n.startswith("__MACOSX")
            ]
            if srt_files:
                return zf.read(srt_files[0]), srt_files[0]
            return zip_bytes, f"{fallback_name}.zip"
        except zipfile.BadZipFile:
            pass
    return zip_bytes, f"{fallback_name}.srt"


def format_subtitle_label(sub: dict, index: int) -> str:
    """يرجّع نصاً قصيراً لعرضه لكل زر في نتائج الترجمة."""
    release = sub.get("releaseInfo", [])
    if isinstance(release, list) and release:
        label = str(release[0])
    else:
        label = sub.get("title") or sub.get("releaseName") or f"ترجمة {index + 1}"
    return f"{index + 1}. {label}"[:60]
