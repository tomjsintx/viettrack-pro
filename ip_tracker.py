from __future__ import annotations

import json
import logging
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import folium
import requests

logger = logging.getLogger(__name__)

# Bản đồ cổng -> tên dịch vụ
SERVICE_MAP: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    6379: "Redis",
    8080: "HTTP-Alt",
    8443: "HTTPS-Alt",
}


def _safe_request(url: str, timeout: int = 10, **kwargs: Any) -> dict | None:
    """Gọi HTTP an toàn, trả về None nếu lỗi."""
    try:
        resp = requests.get(url, timeout=timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Request lỗi %s: %s", url, exc)
        return None


def _query_ip_api(ip: str) -> dict:
    """Truy vấn ip-api.com."""
    data = _safe_request(f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,lat,lon,isp,org,timezone,as,query")
    if not data or data.get("status") != "success":
        return {}
    return {
        "nguon": "ip-api.com",
        "quoc_gia": data.get("country"),
        "vung": data.get("regionName"),
        "thanh_pho": data.get("city"),
        "vi_do": data.get("lat"),
        "kinh_do": data.get("lon"),
        "isp": data.get("isp"),
        "to_chuc": data.get("org"),
        "mui_gio": data.get("timezone"),
        "asn": data.get("as"),
    }


def _query_ipinfo(ip: str, token: str | None = None) -> dict:
    """Truy vấn ipinfo.io."""
    url = f"https://ipinfo.io/{ip}/json"
    if token:
        url += f"?token={token}"
    data = _safe_request(url)
    if not data:
        return {}
    loc = data.get("loc", ",").split(",")
    return {
        "nguon": "ipinfo.io",
        "quoc_gia": data.get("country"),
        "vung": data.get("region"),
        "thanh_pho": data.get("city"),
        "vi_do": float(loc[0]) if len(loc) == 2 and loc[0] else None,
        "kinh_do": float(loc[1]) if len(loc) == 2 and loc[1] else None,
        "isp": data.get("org"),
        "to_chuc": data.get("org"),
        "mui_gio": data.get("timezone"),
    }


def _query_ipgeolocation(ip: str, api_key: str) -> dict:
    """Truy vấn ipgeolocation.io."""
    if not api_key:
        return {}
    data = _safe_request(f"https://api.ipgeolocation.io/ipgeo?apiKey={api_key}&ip={ip}")
    if not data:
        return {}
    return {
        "nguon": "ipgeolocation.io",
        "quoc_gia": data.get("country_name"),
        "vung": data.get("state_prov"),
        "thanh_pho": data.get("city"),
        "vi_do": float(data["latitude"]) if data.get("latitude") else None,
        "kinh_do": float(data["longitude"]) if data.get("longitude") else None,
        "isp": data.get("isp"),
        "to_chuc": data.get("organization"),
        "mui_gio": data.get("time_zone", {}).get("name") if isinstance(data.get("time_zone"), dict) else None,
    }


def get_ip_info(ip: str, api_keys: dict | None = None) -> dict:
    """
    Truy vấn đa nguồn để lấy thông tin IP.

    Args:
        ip: Địa chỉ IP cần tra cứu.
        api_keys: Dict chứa API keys (tùy chọn).

    Returns:
        Dict tổng hợp thông tin IP.
    """
    api_keys = api_keys or {}
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_query_ip_api, ip): "ip-api",
            pool.submit(_query_ipinfo, ip, api_keys.get("ipinfo")): "ipinfo",
            pool.submit(_query_ipgeolocation, ip, api_keys.get("ipgeolocation", "")): "ipgeolocation",
        }
        for fut in as_completed(futures):
            try:
                res = fut.result()
                if res:
                    results.append(res)
            except Exception as exc:
                logger.warning("Lỗi truy vấn %s: %s", futures[fut], exc)

    # Hợp nhất: ưu tiên dữ liệu từ nguồn có nhiều trường hơn
    merged: dict[str, Any] = {"ip": ip, "cac_nguon": [r["nguon"] for r in results]}
    for key in ("quoc_gia", "vung", "thanh_pho", "vi_do", "kinh_do", "isp", "to_chuc", "mui_gio", "asn"):
        for r in results:
            if r.get(key):
                merged[key] = r[key]
                break

    return merged


def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Chuyển tọa độ thành địa chỉ đầy đủ qua Nominatim.

    Args:
        lat: Vĩ độ.
        lon: Kinh độ.

    Returns:
        Dict địa chỉ: số nhà, đường, phường/xã, quận/huyện, thành phố, tỉnh, quốc gia.
    """
    url = (
        f"https://nominatim.openstreetmap.org/reverse?"
        f"format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    )
    headers = {"User-Agent": "VietTrack-Pro/1.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Reverse geocode lỗi: %s", exc)
        return {}

    addr = data.get("address", {})
    return {
        "dia_chi_day_du": data.get("display_name"),
        "so_nha": addr.get("house_number"),
        "duong": addr.get("road"),
        "phuong_xa": addr.get("suburb") or addr.get("village") or addr.get("hamlet"),
        "quan_huyen": addr.get("city_district") or addr.get("county"),
        "thanh_pho": addr.get("city") or addr.get("town"),
        "tinh": addr.get("state"),
        "quoc_gia": addr.get("country"),
        "ma_buu_chinh": addr.get("postcode"),
    }


def create_map(lat: float, lon: float, output_file: str, popup: str = "") -> str:
    """
    Tạo bản đồ HTML với marker tại tọa độ.

    Args:
        lat: Vĩ độ.
        lon: Kinh độ.
        output_file: Đường dẫn file HTML xuất ra.
        popup: Nội dung popup.

    Returns:
        Đường dẫn file đã tạo.
    """
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles="OpenStreetMap")
    folium.Marker(
        [lat, lon],
        popup=popup or f"{lat}, {lon}",
        tooltip="Vị trí",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)
    folium.Circle([lat, lon], radius=200, color="blue", fill=True, fill_opacity=0.2).add_to(m)
    m.save(output_file)
    return output_file


def _grab_banner(sock: socket.socket) -> str:
    """Lấy banner từ socket nếu có."""
    try:
        sock.settimeout(2)
        banner = sock.recv(1024)
        return banner.decode("utf-8", errors="ignore").strip()
    except (socket.timeout, OSError):
        return ""


def _scan_one_port(ip: str, port: int, timeout: float = 2.0) -> dict:
    """Quét một cổng đơn lẻ."""
    result = {"cong": port, "dich_vu": SERVICE_MAP.get(port, "Unknown"), "trang_thai": "đóng", "banner": ""}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            if sock.connect_ex((ip, port)) == 0:
                result["trang_thai"] = "mở"
                result["banner"] = _grab_banner(sock)
    except OSError as exc:
        logger.debug("Lỗi quét cổng %s: %s", port, exc)
    return result


def scan_ports(ip: str, ports: list[int] | None = None, timeout: float = 2.0) -> list[dict]:
    """
    Quét cổng đa luồng.

    Args:
        ip: Địa chỉ IP mục tiêu.
        ports: Danh sách cổng. Mặc định là các cổng phổ biến.
        timeout: Timeout mỗi cổng (giây).

    Returns:
        Danh sách dict kết quả quét.
    """
    ports = ports or [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 3306, 3389, 5432, 6379, 8080, 8443]
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=50) as pool:
        futures = {pool.submit(_scan_one_port, ip, p, timeout): p for p in ports}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                logger.warning("Lỗi quét cổng %s: %s", futures[fut], exc)
    results.sort(key=lambda r: r["cong"])
    return results


def shodan_lookup(ip: str, api_key: str) -> dict:
    """
    Tra cứu thông tin IP qua Shodan.

    Args:
        ip: Địa chỉ IP.
        api_key: Shodan API key.

    Returns:
        Dict thông tin Shodan.
    """
    if not api_key:
        return {"loi": "Chưa cấu hình Shodan API key"}
    try:
        import shodan
        api = shodan.Shodan(api_key)
        host = api.host(ip)
        return {
            "os": host.get("os"),
            "to_chuc": host.get("org"),
            "isp": host.get("isp"),
            "quoc_gia": host.get("country_name"),
            "thanh_pho": host.get("city"),
            "cac_cong_mo": [f"{item['port']}/{item.get('transport', 'tcp')}" for item in host.get("data", [])],
            "lo_hong": host.get("vulns", []),
            "cap_nhat_cuoi": host.get("last_update"),
        }
    except Exception as exc:
        logger.warning("Shodan lỗi: %s", exc)
        return {"loi": str(exc)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_ip = input("Nhập IP: ").strip()
    print(json.dumps(get_ip_info(test_ip), ensure_ascii=False, indent=2))
    time.sleep(1)
    print(json.dumps(scan_ports(test_ip), ensure_ascii=False, indent=2))
