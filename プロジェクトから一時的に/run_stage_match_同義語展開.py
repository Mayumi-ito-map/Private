"""
司令塔② : judge==0 のみ段階的正規化マッチング（Stage1→2→3）

責務：
- output_match/*.xlsx（司令塔①の結果）を入力とする
- 列 normalized_name / judge を使用。judge=="0" の行のみ対象
- geonames_master.pkl を国コード（海外領土対応）で読み、Stage1→2→3 でマッチング
- マッチしたGeoNames情報（geonameid, lat, lon 等）を Stage1_hit / Stage2_hit / Stage3_hit に記録
- output_match_results に各国 _result.xlsx、world_summary.xlsx を出力
"""
from __future__ import annotations

import ast
import json
import pandas as pd
from pathlib import Path

from geonames_loader import load_master_pkl, get_geonames_for_country
from normalizers.expand_synonyms import expand_candidates_synonyms
from normalizers.stage_matcher import (
    normalize_stage1,
    normalize_stage2,
    normalize_stage3,
)

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "output_match"
OUTPUT_DIR = BASE_DIR / "output_match_results"
CONFIG_DIR = BASE_DIR / "config"
OVERSEAS_FILE = CONFIG_DIR / "overseas_territories.json"
OUTPUT_DIR.mkdir(exist_ok=True)


# =========================================================
# 海外領土
# =========================================================

def load_overseas_map():
    if not OVERSEAS_FILE.exists():
        return {}
    with open(OVERSEAS_FILE, encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# Stageマップ構築（geonames_loader の records から）
# =========================================================

def build_stage_maps(records: list[dict]):
    """
    name / asciiname / alternatenames を正規化キーにし、
    Stage1/2/3 それぞれのキーでレコードを引ける辞書を返す。
    """
    maps = {"stage1": {}, "stage2": {}, "stage3": {}}
    for record in records:
        names = []
        if record.get("name"):
            names.append(record["name"])
        if record.get("asciiname"):
            names.append(record["asciiname"])
        alt = record.get("alternatenames")
        if isinstance(alt, list):
            names.extend(alt)
        elif isinstance(alt, str) and alt:
            names.extend([a.strip() for a in alt.split(",") if a.strip()])
        for n in names:
            if not n:
                continue
            s1 = normalize_stage1(n)
            s2 = normalize_stage2(n)
            s3 = normalize_stage3(n)
            maps["stage1"].setdefault(s1, []).append(record)
            maps["stage2"].setdefault(s2, []).append(record)
            maps["stage3"].setdefault(s3, []).append(record)
    return maps


# =========================================================
# normalized_name の読み込み（リスト形式対応）
# =========================================================

def parse_normalized_name(value) -> list:
    """Excel から読み込んだ normalized_name をリストに変換する。"""
    if pd.isna(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return parsed
            return [parsed] if parsed else []
        except (ValueError, SyntaxError):
            return [s] if s else []
    return [value] if value else []


# =========================================================
# 1ファイル処理
# =========================================================

def process_excel(path: Path, overseas_map: dict, db: dict):
    print(f"processing: {path.name}")

    df = pd.read_excel(path, engine="openpyxl")
    if "normalized_name" not in df.columns or "judge" not in df.columns:
        print("  Skipping: missing normalized_name or judge")
        return None

    country_code = path.stem.split("_")[1] if "_" in path.stem else ""
    if not country_code:
        print("  Skipping: no country code in filename")
        return None

    placename_dict, records, gdf = get_geonames_for_country(db, country_code, overseas_map)
    stage_maps = build_stage_maps(records)

    df["Stage1_hit"] = None
    df["Stage2_hit"] = None
    df["Stage3_hit"] = None

    total_candidates = 0
    total_rows = 0  # 行数ベース（hit_0 と一致させるため）
    rows_with_hit = 0  # 行単位：Stage1/2/3 のどれかで 1件でもヒットした行数
    stage1_count = 0
    stage2_count = 0
    stage3_count = 0
    still_0_count = 0

    target_rows = df[df["judge"].astype(str).str.strip() == "0"].index
    total_rows = len(target_rows)  # 行数ベース（hit_0 と一致させるため）

    for idx in target_rows:
        raw = df.at[idx, "normalized_name"]
        candidates = parse_normalized_name(raw)
        if not candidates:
            continue
        # 一般語・接頭辞の同義語展開（Mt/Mount, St/Saint, Jebel/Jabal 等）で候補を増やす
        candidates = expand_candidates_synonyms(candidates)

        stage1_hits = {}
        stage2_hits = {}
        stage3_hits = {}

        for candidate in candidates:
            total_candidates += 1
            matched = False
            matched_stage = None

            for stage_name, normalizer in [
                ("stage1", normalize_stage1),
                ("stage2", normalize_stage2),
                ("stage3", normalize_stage3),
            ]:
                key = normalizer(candidate)
                hits = stage_maps[stage_name].get(key)
                if hits:
                    for r in hits:
                        geoid = r.get("geonameid")
                        if not geoid:
                            continue
                        record_copy = dict(r)
                        if stage_name == "stage1":
                            stage1_hits[geoid] = record_copy
                        elif stage_name == "stage2":
                            stage2_hits[geoid] = record_copy
                        else:
                            stage3_hits[geoid] = record_copy
                    matched = True
                    matched_stage = stage_name
                    break

            if matched:
                if matched_stage == "stage1":
                    stage1_count += 1
                elif matched_stage == "stage2":
                    stage2_count += 1
                else:
                    stage3_count += 1
            else:
                still_0_count += 1

        if stage1_hits:
            df.at[idx, "Stage1_hit"] = list(stage1_hits.values())
        if stage2_hits:
            df.at[idx, "Stage2_hit"] = list(stage2_hits.values())
        if stage3_hits:
            df.at[idx, "Stage3_hit"] = list(stage3_hits.values())

        # 行単位：この行で 1件でもヒットしていればカウント
        if stage1_hits or stage2_hits or stage3_hits:
            rows_with_hit += 1

    rows_still_0 = total_rows - rows_with_hit  # 行単位でまだヒットなし

    if total_candidates > 0:
        s1p = round(stage1_count / total_candidates * 100, 1)
        s2p = round(stage2_count / total_candidates * 100, 1)
        s3p = round(stage3_count / total_candidates * 100, 1)
        s0p = round(still_0_count / total_candidates * 100, 1)
    else:
        s1p = s2p = s3p = s0p = 0.0

    # 出力ファイル名: 入力が cn002_AZ_アゼルバイジャン_result.xlsx のとき
    # 出力は output_match_results/cn002_AZ_アゼルバイジャン_result.xlsx（拡張子なしで country としても使用）
    out_name = f"{path.stem}.xlsx"
    df.to_excel(OUTPUT_DIR / out_name, index=False)

    return {
        "country": path.stem,
        "total_0_target": total_rows,  # 行数ベース（hit_0 と一致）
        "rows_with_hit": rows_with_hit,  # 行単位：1件でもヒットした行数
        "rows_still_0": rows_still_0,  # 行単位：まだヒットなし（still_0 の行数）
        "total_candidates": total_candidates,  # 候補数（参考情報）
        "stage1": stage1_count,
        "stage1(%)": s1p,
        "stage2": stage2_count,
        "stage2(%)": s2p,
        "stage3": stage3_count,
        "stage3(%)": s3p,
        "still_0": still_0_count,
        "still_0(%)": s0p,
    }


# =========================================================
# メイン
# =========================================================

def main():
    print("Loading geonames_master.pkl (once)...")
    db = load_master_pkl()
    print("Done.")

    overseas_map = load_overseas_map()
    stats = []

    for path in sorted(INPUT_DIR.glob("cn*_*.xlsx")):
        if path.name.startswith("~$"):
            continue
        s = process_excel(path, overseas_map, db)
        if s:
            stats.append(s)

    if stats:
        df_summary = pd.DataFrame(stats)
        df_summary.to_excel(OUTPUT_DIR / "world_summary.xlsx", index=False)
        print("world_summary.xlsx saved")


if __name__ == "__main__":
    main()
