"""
Module chuyển đổi tọa độ ↔ địa chỉ.
Sử dụng Nominatim OpenStreetMap, không cần API key.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
HEADERS = {"User-Agent": "VietTrack-Pro/1.0 (contact: LO)"}


def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Tọa độ → địa chỉ đầy đủ.

    Args:
        lat: Vĩ độ.
        lon: Kinh độ.

    Returns:
        Dict địa chỉ chi tiết.
    """
    try:
        resp = requests.get(
            f"{NOMINATIM_BASE}/reverse",
            params={"format": "json", "lat": lat, "lon": lon, "zoom": 18, "addressdetails": 1},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("Reverse geocode lỗi: %s", exc)
        return {"loi": str(exc)}

    a = data.get("address", {})
    return {
        "vi_do": lat,
        "kinh_do": lon,
        "dia_chi_day_du": data.get("display_name"),
        "so_nha": a.get("house_number"),
        "duong": a.get("road") or a.get("pedestrian") or a.get("footway"),
        "phuong_xa": a.get("suburb") or a.get("village") or a.get("hamlet") or a.get("quarter"),
        "quan_huyen": a.get("city_district") or a.get("county") or a.get("district"),
        "thanh_pho": a.get("city") or a.get("town") or a.get("municipality"),
        "tinh": a.get("state") or a.get("province"),
        "quoc_gia": a.get("country"),
        "ma_quoc_gia": a.get("country_code"),
        "ma_buu_chinh": a.get("postcode"),
        "toa_do_osm": data.get("osm_type"),
        "loai": data.get("type"),
    }


def forward_geocode(address: str, limit: int = 5) -> list[dict]:
    """
    Địa chỉ → tọa độ.

    Args:
        address: Địa chỉ cần tìm.
        limit: Số kết quả tối đa.

    Returns:
        Danh sách dict kết quả.
    """
    try:
        resp = requests.get(
            f"{NOMINATIM_BASE}/search",
            params={"format": "json", "q": address, "limit": limit, "addressdetails": 1},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.warning("Forward geocode lỗi: %s", exc)
        return [{"loi": str(exc)}]

    results: list[dict] = []
    for item in data:
        a = item.get("address", {})
        results.append({
            "dia_chi_day_du": item.get("display_name"),
            "vi_do": float(item["lat"]) if item.get("lat") else None,
            "kinh_do": float(item["lon"]) if item.get("lon") else None,
            "so_nha": a.get("house_number"),
            "duong": a.get("road"),
            "phuong_xa": a.get("suburb") or a.get("village"),
            "quan_huyen": a.get("city_district") or a.get("county"),
            "thanh_pho": a.get("city") or a.get("town"),
            "tinh": a.get("state"),
            "quoc_gia": a.get("country"),
            "ma_buu_chinh": a.get("postcode"),
        })
    return results


def infer_house_number(lat: float, lon: float) -> str:
    """
    Suy luận số nhà từ tọa độ (kết hợp OSM và dữ liệu lân cận).

    Args:
        lat: Vĩ độ.
        lon: Kinh độ.

    Returns:
        Số nhà ước tính hoặc rỗng nếu không tìm thấy.
    """
    info = reverse_geocode(lat, lon)
    if info.get("so_nha"):
        return info["so_nha"]

    # Fallback: tìm kiếm trong bán kính 50m
    try:
        resp = requests.get(
            f"{NOMINATIM_BASE}/reverse",
            params={"format": "json", "lat": lat, "lon": lon, "zoom": 19},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("address", {}).get("house_number", "")
    except requests.RequestException:
        return ""


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    lat = float(input("Nhập vĩ độ: ").strip())
    lon = float(input("Nhập kinh độ: ").strip())
    print(json.dumps(reverse_geocode(lat, lon), ensure_ascii=False, indent=2))
