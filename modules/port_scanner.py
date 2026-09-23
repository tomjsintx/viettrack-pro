"""
Module quét cổng đa luồng.
"""
from __future__ import annotations

import logging
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

DEFAULT_PORTS = [21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 3306, 3389, 5432, 6379, 8080, 8443]

SERVICE_MAP = {
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


def _scan_one(ip: str, port: int, timeout: float) -> dict:
    """Quét một cổng."""
    result = {
        "cong": port,
        "dich_vu": SERVICE_MAP.get(port, "Unknown"),
        "trang_thai": "đóng",
        "banner": "",
    }
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((ip, port)) == 0:
                result["trang_thai"] = "mở"
                try:
                    s.settimeout(2)
                    banner = s.recv(1024).decode("utf-8", errors="ignore").strip()
                    result["banner"] = banner[:200]
                except (socket.timeout, OSError):
                    pass
    except OSError as exc:
        logger.debug("Lỗi cổng %d: %s", port, exc)
    return result


def scan_ports(ip: str, ports: list[int] | None = None, timeout: float = 2.0) -> dict:
    """
    Quét nhiều cổng song song.

    Args:
        ip: Địa chỉ IP.
        ports: Danh sách cổng (mặc định DEFAULT_PORTS).
        timeout: Timeout mỗi cổng (giây).

    Returns:
        Dict kết quả: ip, so_cong_mo, chi_tiet.
    """
    ports = ports or DEFAULT_PORTS
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=60) as pool:
        futures = {pool.submit(_scan_one, ip, p, timeout): p for p in ports}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                logger.warning("Lỗi quét %d: %s", futures[fut], exc)

    results.sort(key=lambda r: r["cong"])
    opened = [r for r in results if r["trang_thai"] == "mở"]
    return {
        "ip": ip,
        "so_cong_quet": len(ports),
        "so_cong_mo": len(opened),
        "chi_tiet": results,
    }


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    ip = input("Nhập IP: ").strip()
    print(json.dumps(scan_ports(ip), ensure_ascii=False, indent=2))
