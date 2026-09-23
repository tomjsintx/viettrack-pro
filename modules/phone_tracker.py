from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import phonenumbers
from phonenumbers import carrier, geocoder, timezone as pn_timezone
import requests

logger = logging.getLogger(__name__)


def _get_offline_info(phone: str, country_code: str = "VN") -> dict:
    """Lấy thông tin số điện thoại offline qua phonenumbers."""
    try:
        parsed = phonenumbers.parse(phone, country_code)
    except phonenumbers.NumberParseException as exc:
        return {"loi": f"Không parse được số: {exc}"}

    valid = phonenumbers.is_valid_number(parsed)
    possible = phonenumbers.is_possible_number(parsed)

    line_type_map = {
        phonenumbers.PhoneNumberType.MOBILE: "Di động",
        phonenumbers.PhoneNumberType.FIXED_LINE: "Cố định",
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Cố định hoặc di động",
        phonenumbers.PhoneNumberType.TOLL_FREE: "Miễn phí",
        phonenumbers.PhoneNumberType.PREMIUM_RATE: "Cao cấp",
        phonenumbers.PhoneNumberType.VOIP: "VoIP",
        phonenumbers.PhoneNumberType.UNKNOWN: "Không xác định",
    }
    number_type = phonenumbers.number_type(parsed)

    return {
        "so_dien_thoai": phone,
        "dinh_dang_e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
        "dinh_dang_quoc_te": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "ma_quoc_gia": parsed.country_code,
        "quoc_gia": phonenumbers.region_code_for_number(parsed),
        "nha_mang": carrier.name_for_number(parsed, "vi") or carrier.name_for_number(parsed, "en"),
        "loai_duong_day": line_type_map.get(number_type, "Không rõ"),
        "vi_tri": geocoder.description_for_number(parsed, "vi") or geocoder.description_for_number(parsed, "en"),
        "mui_gio": list(pn_timezone.time_zones_for_number(parsed)),
        "hop_le": valid,
        "kha_thi": possible,
    }


def _query_numverify(phone: str, api_key: str) -> dict:
    """Truy vấn Numverify API."""
    if not api_key:
        return {}
    try:
        resp = requests.get(
            "http://apilayer.net/api/validate",
            params={"access_key": api_key, "number": phone, "format": 1},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("valid"):
            return {}
        return {
            "numverify_carrier": data.get("carrier"),
            "numverify_line_type": data.get("line_type"),
            "numverify_location": data.get("location"),
            "numverify_country": data.get("country_name"),
        }
    except requests.RequestException as exc:
        logger.warning("Numverify lỗi: %s", exc)
        return {}


def _query_abstractapi(phone: str, api_key: str) -> dict:
    """Truy vấn AbstractAPI Phone Validation."""
    if not api_key:
        return {}
    try:
        resp = requests.get(
            "https://phonevalidation.abstractapi.com/v1/",
            params={"api_key": api_key, "phone": phone},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "abstract_valid": data.get("valid"),
            "abstract_format": data.get("format", {}).get("international"),
            "abstract_country": data.get("country", {}).get("name") if isinstance(data.get("country"), dict) else None,
            "abstract_location": data.get("location"),
            "abstract_carrier": data.get("carrier"),
            "abstract_line_type": data.get("type"),
        }
    except requests.RequestException as exc:
        logger.warning("AbstractAPI lỗi: %s", exc)
        return {}


def _query_omkarcloud(phone: str) -> dict:
    """Truy vấn OmkarCloud phone lookup (miễn phí, không cần key)."""
    try:
        resp = requests.get(
            "https://phone-number-lookup-api.omkar.cloud/phone-lookup",
            params={"phone": phone},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "omkar_carrier": data.get("carrier"),
            "omkar_line_type": data.get("line_type"),
        }
    except requests.RequestException as exc:
        logger.debug("OmkarCloud lỗi: %s", exc)
        return {}


def get_phone_info(phone: str, country_code: str = "VN", api_keys: dict | None = None) -> dict:
    """
    Tra cứu thông tin số điện thoại đa nguồn.

    Args:
        phone: Số điện thoại.
        country_code: Mã quốc gia mặc định (VN).
        api_keys: Dict chứa API keys.

    Returns:
        Dict tổng hợp thông tin số.
    """
    api_keys = api_keys or {}
    result: dict[str, Any] = _get_offline_info(phone, country_code)

    if "loi" in result:
        return result

    # Chuẩn hóa số về E.164 để gửi API
    e164 = result["dinh_dang_e164"]

    result.update(_query_numverify(e164, api_keys.get("numverify", "")))
    result.update(_query_abstractapi(e164, api_keys.get("abstractapi", "")))
    result.update(_query_omkarcloud(e164))

    return result


def batch_lookup(file_path: str, output_csv: str, country_code: str = "VN", api_keys: dict | None = None) -> list[dict]:
    """
    Tra cứu hàng loạt số từ file txt.

    Args:
        file_path: File txt chứa mỗi dòng 1 số.
        output_csv: File CSV xuất kết quả.
        country_code: Mã quốc gia mặc định.
        api_keys: API keys.

    Returns:
        Danh sách dict kết quả.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    numbers = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    results: list[dict] = []

    for idx, num in enumerate(numbers, 1):
        logger.info("[%d/%d] Đang tra: %s", idx, len(numbers), num)
        try:
            results.append(get_phone_info(num, country_code, api_keys))
        except Exception as exc:
            logger.error("Lỗi tra %s: %s", num, exc)
            results.append({"so_dien_thoai": num, "loi": str(exc)})

    if results:
        keys = sorted({k for r in results for k in r.keys()})
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in results:
                writer.writerow(r)

    return results


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    sdt = input("Nhập số điện thoại: ").strip()
    print(json.dumps(get_phone_info(sdt), ensure_ascii=False, indent=2))
