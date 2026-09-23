from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
    )
}


def _check_url(name: str, url: str, headers: dict | None = None, ok_codes: tuple = (200,)) -> dict:
    """Kiểm tra một URL có tồn tại không."""
    try:
        resp = requests.get(url, headers=headers or HEADERS, timeout=10, allow_redirects=True)
        exists = resp.status_code in ok_codes
        return {"nen_tang": name, "url": url, "ton_tai": exists, "status_code": resp.status_code}
    except requests.RequestException as exc:
        return {"nen_tang": name, "url": url, "ton_tai": False, "loi": str(exc)}


def check_social(phone: str) -> dict:
    """
    Kiểm tra sự tồn tại tài khoản trên nhiều nền tảng.

    Args:
        phone: Số điện thoại (E.164 hoặc quốc gia).

    Returns:
        Dict kết quả từng nền tảng.
    """
    digits = phone.lstrip("+").replace(" ", "").replace("-", "")
    checks: list[tuple[str, str]] = [
        ("GitHub", f"https://github.com/{digits}"),
        ("Instagram", f"https://www.instagram.com/{digits}/"),
        ("Twitter/X", f"https://twitter.com/{digits}"),
        ("TikTok", f"https://www.tiktok.com/@{digits}"),
        ("Reddit", f"https://www.reddit.com/user/{digits}"),
        ("Pinterest", f"https://www.pinterest.com/{digits}/"),
        ("Medium", f"https://medium.com/@{digits}"),
        ("Twitch", f"https://www.twitch.tv/{digits}"),
        ("LinkedIn", f"https://www.linkedin.com/in/{digits}"),
        ("Telegram", f"https://t.me/+{digits}"),
        ("Zalo", f"https://zalo.me/{digits}"),
        ("Facebook", f"https://www.facebook.com/search/top?q={digits}"),
    ]

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(_check_url, name, url) for name, url in checks]
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                logger.warning("Lỗi check social: %s", exc)

    results.sort(key=lambda r: r["nen_tang"])
    return {
        "so_dien_thoai": phone,
        "ket_qua": results,
        "tong_ton_tai": sum(1 for r in results if r.get("ton_tai")),
    }


def search_google(phone: str, serpapi_key: str) -> list[dict]:
    """
    Tìm kiếm Google qua SerpAPI.

    Args:
        phone: Số điện thoại.
        serpapi_key: SerpAPI key.

    Returns:
        Danh sách kết quả tìm kiếm.
    """
    if not serpapi_key:
        return [{"loi": "Chưa cấu hình SerpAPI key"}]
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={"q": phone, "api_key": serpapi_key, "hl": "vi", "num": 20},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "tieu_de": r.get("title"),
                "link": r.get("link"),
                "trich_doan": r.get("snippet"),
            }
            for r in data.get("organic_results", [])
        ]
    except requests.RequestException as exc:
        logger.warning("SerpAPI lỗi: %s", exc)
        return [{"loi": str(exc)}]


def check_hudson_rock(phone: str) -> dict:
    """
    Kiểm tra số điện thoại có bị lộ qua infostealer qua Hudson Rock.

    Args:
        phone: Số điện thoại.

    Returns:
        Dict kết quả.
    """
    try:
        resp = requests.get(
            "https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-phone",
            params={"phone": phone},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "bi_nhiem": data.get("message") != "No results",
            "du_lieu": data.get("data", {}),
        }
    except requests.RequestException as exc:
        logger.warning("Hudson Rock lỗi: %s", exc)
        return {"loi": str(exc)}


def search_duckduckgo(phone: str) -> list[dict]:
    """
    Tìm kiếm DuckDuckGo (không cần API key).

    Args:
        phone: Số điện thoại.

    Returns:
        Danh sách kết quả.
    """
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": phone},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "lxml")
        results: list[dict] = []
        for item in soup.select(".result")[:15]:
            title = item.select_one(".result__title")
            link = item.select_one(".result__url")
            snippet = item.select_one(".result__snippet")
            if title and link:
                results.append({
                    "tieu_de": title.get_text(strip=True),
                    "link": link.get_text(strip=True),
                    "trich_doan": snippet.get_text(strip=True) if snippet else "",
                })
        return results
    except requests.RequestException as exc:
        logger.warning("DuckDuckGo lỗi: %s", exc)
        return [{"loi": str(exc)}]


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    sdt = input("Nhập số: ").strip()
    print(json.dumps(check_social(sdt), ensure_ascii=False, indent=2))
    print(json.dumps(check_hudson_rock(sdt), ensure_ascii=False, indent=2))
