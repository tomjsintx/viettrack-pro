# VietTrack Pro

Framework tình báo vị trí đa nền tảng, chạy trên Termux (Android) không cần root.

## Tính năng

- Truy vết IP đa nguồn (ip-api, ipinfo, ipgeolocation)
- Reverse geocoding (Nominatim OpenStreetMap)
- Quét cổng đa luồng + banner grab
- Shodan lookup (tùy chọn)
- Truy vết số điện thoại (offline + Numverify + AbstractAPI + OmkarCloud)
- Tìm kiếm qua mạng xã hội (12+ nền tảng)
- Hudson Rock infostealer check
- Trang bẫy thiết bị (Social Engineering) + Cloudflared tunnel + Telegram alert
- Xuất báo cáo JSON / CSV / TXT / HTML với bản đồ

## Cài đặt

```bash
git clone <repo> viettrack-pro
cd viettrack-pro
chmod +x setup.sh
./setup.sh
