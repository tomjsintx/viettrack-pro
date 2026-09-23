#!/data/data/com.termux/files/usr/bin/bash
# VietTrack Pro - Script cài đặt tự động trên Termux
set -e

echo "[*] Cập nhật Termux..."
pkg update && pkg upgrade -y

echo "[*] Cài đặt gói hệ thống..."
pkg install python git openssh cloudflared -y

echo "[*] Nâng cấp pip..."
pip install --upgrade pip

echo "[*] Cài đặt thư viện Python..."
pip install -r requirements.txt

echo "[*] Tạo thư mục output..."
mkdir -p output

echo "[*] Copy file cấu hình mẫu..."
[ -f config/api_keys.json ] || cp config/api_keys.json.example config/api_keys.json
[ -f config/telegram.json ] || cp config/telegram.json.example config/telegram.json

echo "[✓] Hoàn tất! Chạy: python viettrack.py"
