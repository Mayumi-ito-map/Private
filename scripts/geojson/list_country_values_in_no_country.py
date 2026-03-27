"""
geojson/by_region/500_no_country.geojson 内の各 Feature について
properties["country"] の取りうる値と件数を一覧する。
"country"はIOC3桁コード。
（国分類.xlsx のいずれのコードにも一致しなかった行の country 分布確認用）
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def country_label(v: object) -> str:
    if v is None:
        return "<null>"
    s = str(v).strip()
    return "<empty>" if s == "" else s


def main() -> None:
    root = project_root()
    parser = argparse.ArgumentParser(
        description="500_no_country.geojson の country 値の種類と件数を表示する。"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "geojson" / "by_region" / "500_no_country.geojson",
        help="入力 GeoJSON（既定: by_region/500_no_country.geojson）",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="カンマ区切り（country,count）でも出力する",
    )
    args = parser.parse_args()
    path = args.input.expanduser().resolve()

    if not path.is_file():
        raise SystemExit(f"入力が見つかりません: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features") or []
    counts: Counter[str] = Counter()
    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties")
        if not isinstance(props, dict):
            counts["<no properties>"] += 1
            continue
        counts[country_label(props.get("country"))] += 1

    n = sum(counts.values())
    print(f"ファイル: {path}")
    print(f"features 数: {len(features)} / country 集計対象: {n}")
    print(f"country の異なる値の数: {len(counts)}")
    print()
    print(f"{'count':>8}  country")
    print("-" * 72)
    for label, c in counts.most_common():
        # 長い行はそのまま表示（ターミナルで折り返し）
        print(f"{c:8d}  {label}")

    if args.csv:
        print()
        print("--- CSV ---")
        print("country,count")
        for label, c in counts.most_common():
            escaped = label.replace('"', '""')
            print(f'"{escaped}",{c}')


if __name__ == "__main__":
    main()
