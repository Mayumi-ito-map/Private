"""
build_leaflet_index.py

output_leaflet/*.geojson をスキャンし、国一覧と5エリア分類を出力する。
- index.json … 従来どおり（fetch 用）
- data_index.js … HTML と同じフォルダで <script src="data_index.js"> で読む用。
  見本（52.194.188.168）のように「一覧を fetch しない」構成にすると、
  どこで開いてもプルダウンが表示される。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_LEAFLET_DIR = BASE_DIR / "output_leaflet"
INDEX_PATH = OUTPUT_LEAFLET_DIR / "index.json"
DATA_INDEX_JS_PATH = OUTPUT_LEAFLET_DIR / "data_index.js"

# cn 数字の範囲 → エリア（指示通り）
REGIONS = [
    (2, 80, "アジア"),
    (101, 145, "ヨーロッパ"),
    (201, 272, "アフリカ"),
    (301, 323, "北アメリカ・中央アメリカ"),
    (401, 516, "南アメリカ・オセアニア"),
]


def cn_to_region(cn: int) -> str:
    for low, high, name in REGIONS:
        if low <= cn <= high:
            return name
    return "その他"


def main():
    pattern = re.compile(r"^cn(\d+)_", re.IGNORECASE)
    items = []
    for path in sorted(OUTPUT_LEAFLET_DIR.glob("cn*_*.geojson")):
        stem = path.stem
        m = pattern.match(stem)
        cn = int(m.group(1)) if m else 0
        region = cn_to_region(cn)
        items.append({
            "file": path.name,
            "label": stem,
            "cn": cn,
            "region": region,
        })
    items.sort(key=lambda x: x["cn"])

    OUTPUT_LEAFLET_DIR.mkdir(exist_ok=True)
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump({"countries": items}, f, ensure_ascii=False, indent=2)
    print(f"Wrote {INDEX_PATH} ({len(items)} countries)")

    # 見本と同じ方式: 一覧を script で読む用。fetch を使わないので「どこでも表示」できる
    js_content = "// build_leaflet_index.py で生成。leaflet_map.html と同一フォルダに置く\n"
    js_content += "window.LEAFLET_COUNTRY_INDEX = "
    js_content += json.dumps(items, ensure_ascii=False)
    js_content += ";\n"
    with open(DATA_INDEX_JS_PATH, "w", encoding="utf-8") as f:
        f.write(js_content)
    print(f"Wrote {DATA_INDEX_JS_PATH} (for <script src=\"data_index.js\">)")


if __name__ == "__main__":
    main()
