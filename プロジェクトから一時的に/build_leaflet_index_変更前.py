"""
build_leaflet_index_変更前.py（保存用）

※ 変更前の build_leaflet_index.py を別名で保存したものです。
  学習用に残しています。通常の実行には build_leaflet_index.py を使ってください。

元の仕様:
  output_leaflet/*.geojson をスキャンし、国一覧と5エリア分類を index.json に出力する。
  Leaflet 地図のプルダウン用。cn 数字の順で並べ、エリアでグループ化可能にする。

変更後（build_leaflet_index.py）では、上記に加えて data_index.js も生成し、
見本（旧地名地図）と同じ「script で一覧を読む」方式で、どこでも表示できるようにしている。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_LEAFLET_DIR = BASE_DIR / "output_leaflet"
INDEX_PATH = OUTPUT_LEAFLET_DIR / "index.json"

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


if __name__ == "__main__":
    main()
