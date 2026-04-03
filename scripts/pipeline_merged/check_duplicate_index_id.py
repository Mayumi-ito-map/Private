"""
check_duplicate_index_id.py — index_id 重複調査

入力 Excel（excel_local_merged）と GeoJSON（geojson/by_region）の両方で
index_id の重複を調査し、結果をコンソールに出力する。
"""

import json
import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd


def check_excel_duplicates():
    """入力 Excel の index_id 重複を調査。"""
    print("=" * 60)
    print("  調査1: 入力 Excel（excel_local_merged）")
    print("=" * 60)

    excel_dir = PROJECT_ROOT / "excel_local_merged"
    if not excel_dir.exists():
        print(f"  ERROR: {excel_dir} が存在しません")
        return

    INDEX_CANDIDATES = ["index_id", "index_ID", "INDEX_ID"]
    all_ids = []  # (index_id, source_file)

    for path in sorted(excel_dir.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        print(f"  loading: {path.name}", flush=True)
        df = pd.read_excel(path, engine="openpyxl")

        idx_col = None
        for c in INDEX_CANDIDATES:
            if c in df.columns:
                idx_col = c
                break

        if idx_col is None:
            print(f"    WARNING: index_id 列が見つかりません: {list(df.columns)[:10]}")
            continue

        ids = df[idx_col].astype(str).str.strip().tolist()
        print(f"    {idx_col} 列: {len(ids):,} 行, ユニーク: {len(set(ids)):,}")

        # ファイル内の重複
        file_counter = Counter(ids)
        file_dups = {k: v for k, v in file_counter.items() if v > 1}
        if file_dups:
            print(f"    ⚠ ファイル内重複: {len(file_dups)} 件")
            for idx_id, count in sorted(file_dups.items(), key=lambda x: -x[1])[:10]:
                print(f"      {idx_id}: {count} 回")
            if len(file_dups) > 10:
                print(f"      ... 他 {len(file_dups) - 10} 件")
        else:
            print(f"    ファイル内重複: なし")

        for idx_id in ids:
            all_ids.append((idx_id, path.stem))

    # ファイル間の重複
    print(f"\n--- ファイル間の重複チェック ---")
    id_counter = Counter(idx_id for idx_id, _ in all_ids)
    cross_dups = {k: v for k, v in id_counter.items() if v > 1}

    print(f"  全 index_id: {len(all_ids):,}")
    print(f"  ユニーク index_id: {len(id_counter):,}")
    print(f"  ファイル間重複 index_id: {len(cross_dups):,}")

    if cross_dups:
        # どのファイルにまたがっているか表示
        id_to_files = {}
        for idx_id, src in all_ids:
            if idx_id in cross_dups:
                id_to_files.setdefault(idx_id, []).append(src)

        # ファイルの組み合わせ別に集計
        combo_counter = Counter()
        for idx_id, files in id_to_files.items():
            combo = " & ".join(sorted(set(files)))
            combo_counter[combo] += 1

        print(f"\n  重複パターン（どのファイル間で重複しているか）:")
        for combo, count in combo_counter.most_common(20):
            print(f"    {combo}: {count:,} 件")

        print(f"\n  重複 index_id の例（先頭10件）:")
        for idx_id in sorted(cross_dups.keys())[:10]:
            files = id_to_files[idx_id]
            print(f"    {idx_id}: {files}")
    print()


def check_geojson_duplicates():
    """GeoJSON の index_id 重複を調査。"""
    print("=" * 60)
    print("  調査2: GeoJSON（geojson/by_region）")
    print("=" * 60)

    geojson_dir = PROJECT_ROOT / "geojson" / "by_region"
    if not geojson_dir.exists():
        print(f"  ERROR: {geojson_dir} が存在しません")
        return

    all_ids = []  # (index_id, source_file)

    for path in sorted(geojson_dir.glob("cn*.geojson")):
        print(f"  loading: {path.name}", flush=True)
        with open(path, "r", encoding="utf-8") as f:
            gj = json.load(f)

        features = gj.get("features", [])
        ids = []
        missing = 0
        for feat in features:
            idx_id = feat.get("properties", {}).get("index_id")
            if idx_id is None:
                missing += 1
                continue
            ids.append(str(idx_id).strip())

        print(f"    features: {len(features):,}, index_id あり: {len(ids):,}, なし: {missing}")
        print(f"    ユニーク: {len(set(ids)):,}")

        # ファイル内の重複
        file_counter = Counter(ids)
        file_dups = {k: v for k, v in file_counter.items() if v > 1}
        if file_dups:
            print(f"    ⚠ ファイル内重複: {len(file_dups)} 件")
            for idx_id, count in sorted(file_dups.items(), key=lambda x: -x[1])[:10]:
                print(f"      {idx_id}: {count} 回")
            if len(file_dups) > 10:
                print(f"      ... 他 {len(file_dups) - 10} 件")
        else:
            print(f"    ファイル内重複: なし")

        for idx_id in ids:
            all_ids.append((idx_id, path.stem))

    # ファイル間の重複
    print(f"\n--- ファイル間の重複チェック ---")
    id_counter = Counter(idx_id for idx_id, _ in all_ids)
    cross_dups = {k: v for k, v in id_counter.items() if v > 1}

    print(f"  全 index_id: {len(all_ids):,}")
    print(f"  ユニーク index_id: {len(id_counter):,}")
    print(f"  ファイル間重複 index_id: {len(cross_dups):,}")

    if cross_dups:
        id_to_files = {}
        for idx_id, src in all_ids:
            if idx_id in cross_dups:
                id_to_files.setdefault(idx_id, []).append(src)

        combo_counter = Counter()
        for idx_id, files in id_to_files.items():
            combo = " & ".join(sorted(set(files)))
            combo_counter[combo] += 1

        print(f"\n  重複パターン（どのファイル間で重複しているか）:")
        for combo, count in combo_counter.most_common(20):
            print(f"    {combo}: {count:,} 件")

        print(f"\n  重複 index_id の例（先頭10件）:")
        for idx_id in sorted(cross_dups.keys())[:10]:
            files = id_to_files[idx_id]
            print(f"    {idx_id}: {files}")
    print()


def check_output_duplicates():
    """出力 Excel（各パイプライン）の index_id 重複を調査。"""
    print("=" * 60)
    print("  調査3: 各パイプライン出力の重複")
    print("=" * 60)

    INDEX_CANDIDATES = ["index_id", "index_ID", "INDEX_ID"]

    targets = [
        ("① 司令塔①(cate)", PROJECT_ROOT / "output_match_alternatenames_cate", "all"),
        ("③ 司令塔②", PROJECT_ROOT / "output_match_results", None),
        ("② Google API", PROJECT_ROOT / "output_google_api_match", "all"),
        ("④ 全世界", PROJECT_ROOT / "output_match_worldwide_distance", None),
        ("⑤ フィルタなし", PROJECT_ROOT / "output_match_alternatenames_base", "all"),
    ]

    for label, dirpath, sheet in targets:
        print(f"\n  --- {label}: {dirpath.name}/ ---")
        if not dirpath.exists():
            print(f"    ディレクトリなし")
            continue

        all_ids = []
        for path in sorted(dirpath.glob("*.xlsx")):
            if path.name.startswith("~$"):
                continue
            if path.stem in ("tower2_world_summary",):
                continue
            try:
                if sheet:
                    df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
                else:
                    df = pd.read_excel(path, engine="openpyxl")
            except Exception as e:
                print(f"    ERROR reading {path.name}: {e}")
                continue

            idx_col = None
            for c in INDEX_CANDIDATES:
                if c in df.columns:
                    idx_col = c
                    break
            if idx_col is None:
                print(f"    {path.name}: index_id 列なし")
                continue

            ids = df[idx_col].astype(str).str.strip().tolist()
            n_unique = len(set(ids))
            n_dup = len(ids) - n_unique
            dup_mark = f" ⚠ ファイル内重複 {n_dup}" if n_dup > 0 else ""
            print(f"    {path.name}: {len(ids):,} 行, ユニーク: {n_unique:,}{dup_mark}")

            for idx_id in ids:
                all_ids.append((idx_id, path.stem))

        if all_ids:
            id_counter = Counter(idx_id for idx_id, _ in all_ids)
            cross_dups = {k: v for k, v in id_counter.items() if v > 1}
            n_file_internal = sum(1 for idx_id, _ in all_ids if id_counter[idx_id] > 1)
            print(f"    合計: {len(all_ids):,} 行, ユニーク: {len(id_counter):,}, ファイル間重複ID: {len(cross_dups):,}")


if __name__ == "__main__":
    check_excel_duplicates()
    check_geojson_duplicates()
    check_output_duplicates()
