"""
Module xuất báo cáo đa định dạng.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _flatten(d: dict, parent: str = "") -> dict:
    """Làm phẳng dict lồng nhau để xuất CSV."""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        key = f"{parent}.{k}" if parent else k
        if isinstance(v, dict):
            items.extend(_flatten(v, key).items())
        elif isinstance(v, list):
            items.append((key, json.dumps(v, ensure_ascii=False)))
        else:
            items.append((key, v))
    return dict(items)


def generate_json(data: dict, output: Path) -> str:
    """Xuất JSON."""
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


def generate_csv(data: dict, output: Path) -> str:
    """Xuất CSV."""
    flat = _flatten(data)
    with open(output, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["truong", "gia_tri"])
        for k, v in flat.items():
            writer.writerow([k, v])
    return str(output)


def generate_txt(data: dict, output: Path) -> str:
    """Xuất TXT dạng cây."""
    lines: list[str] = []

    def walk(obj: Any, indent: int = 0) -> None:
        pad = "  " * indent
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    lines.append(f"{pad}{k}:")
                    walk(v, indent + 1)
                else:
                    lines.append(f"{pad}{k}: {v}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                lines.append(f"{pad}[{i}]")
                walk(item, indent + 1)
        else:
            lines.append(f"{pad}{obj}")

    walk(data)
    output.write_text("\n".join(lines), encoding="utf-8")
    return str(output)


def generate_html(data: dict, output: Path, map_file: str | None = None) -> str:
    """Xuất HTML có bảng và nhúng bản đồ (nếu có)."""
    rows = "".join(
        f"<tr><td>{k}</td><td><pre>{json.dumps(v, ensure_ascii=False, indent=2) if isinstance(v, (dict, list)) else v}</pre></td></tr>"
        for k, v in data.items()
    )
    map_block = ""
    if map_file and Path(map_file).exists():
        map_html = Path(map_file).read_text(encoding="utf-8")
        map_block = f"<div class='map'>{map_html}</div>"

    html = f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<title>VietTrack Pro — Báo cáo</title>
<style>
  body {{ font-family: -apple-system, sans-serif; background: #0d1117; color: #e6edf3; padding: 30px; }}
  h1 {{ color: #58a6ff; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; background: #161b22; border-radius: 8px; overflow: hidden; }}
  td {{ padding: 12px 16px; border-bottom: 1px solid #21262d; vertical-align: top; }}
  td:first-child {{ font-weight: 600; color: #8b949e; width: 220px; }}
  pre {{ margin: 0; white-space: pre-wrap; word-break: break-all; font-size: 13px; }}
  .map {{ margin-top: 24px; border-radius: 8px; overflow: hidden; height: 500px; }}
  .map iframe {{ width: 100%; height: 100%; border: 0; }}
  .foot {{ margin-top: 24px; color: #6e7681; font-size: 12px; }}
</style></head>
<body>
<h1>Báo cáo VietTrack Pro</h1>
<p style="color:#8b949e;">Thời điểm: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<table>{rows}</table>
{map_block}
<div class="foot">Tạo bởi VietTrack Pro</div>
</body></html>"""
    output.write_text(html, encoding="utf-8")
    return str(output)


def generate_report(data: dict, fmt: str = "json", output_dir: str = "output", map_file: str | None = None) -> str:
    """
    Tạo báo cáo theo định dạng yêu cầu.

    Args:
        data: Dict dữ liệu.
        fmt: 'json', 'csv', 'txt', 'html'.
        output_dir: Thư mục xuất.
        map_file: File bản đồ HTML (cho định dạng html).

    Returns:
        Đường dẫn file đã tạo.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = out_dir / f"report_{ts}.{fmt}"

    if fmt == "json":
        return generate_json(data, output)
    if fmt == "csv":
        return generate_csv(data, output)
    if fmt == "txt":
        return generate_txt(data, output)
    if fmt == "html":
        return generate_html(data, output, map_file)
    raise ValueError(f"Định dạng không hỗ trợ: {fmt}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sample = {"ip": "8.8.8.8", "quoc_gia": "US", "isp": "Google LLC"}
    print(generate_report(sample, "txt"))
