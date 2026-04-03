"""
司令塔②（合体Excel版）: judge==0 の行を Stage1→2→3 でマッチング

入力: output_match_alternatenames_cate/*.xlsx（司令塔①の出力）
出力: output_match_results/

国コードは Excel の cc 列から取得する。
入力ファイルはエリア別でも国別でも、列名が同一であれば動作する。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import ast
import json
import pandas as pd

from geonames_loader import load_master_pkl, get_geonames_for_country
from utils import is_excel_lock_file
from normalizers.stage_matcher import normalize_stage1, normalize_stage2, normalize_stage3

BASE_DIR = PROJECT_ROOT
INPUT_DIR = BASE_DIR / "output_match_alternatenames_cate"
OUTPUT_DIR = BASE_DIR / "output_match_results"
CONFIG_DIR = BASE_DIR / "config"
OVERSEAS_FILE = CONFIG_DIR / "overseas_territories.json"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_overseas_map():
    if not OVERSEAS_FILE.exists():
        return {}
    with open(OVERSEAS_FILE, encoding="utf-8") as f:
        return json.load(f)


def build_stage_maps(records: list[dict]):
    """name / alternatenames から Stage1/2/3 の正規化キーで辞書を構築。asciiname は使用しない。"""
    maps = {"stage1": {}, "stage2": {}, "stage3": {}}
    for record in records:
        names = []
        if record.get("name"):
            names.append(record["name"])
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


def parse_edited_name(value) -> list:
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


def _build_stage_maps_for_cc(cc: str, overseas_map: dict, db: dict,
                              _cache: dict = {}) -> dict:
    """国コード cc に対応する Stage1/2/3 マップを構築（キャッシュ付き）。"""
    if cc in _cache:
        return _cache[cc]
    placename_dict, records, gdf = get_geonames_for_country(db, cc, overseas_map)
    stage_maps = build_stage_maps(records)
    _cache[cc] = stage_maps
    return stage_maps


def _match_row(idx, df, stage_maps):
    """1行の judge==0 行に対して Stage1→2→3 マッチングを実行。"""
    raw = df.at[idx, "edited_name"]
    candidates = parse_edited_name(raw)
    if not candidates:
        return None

    stage1_hits = {}
    stage2_hits = {}
    stage3_hits = {}
    s1 = s2 = s3 = s0 = 0

    for candidate in candidates:
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
                s1 += 1
            elif matched_stage == "stage2":
                s2 += 1
            else:
                s3 += 1
        else:
            s0 += 1

    if stage1_hits:
        df.at[idx, "Stage1_hit"] = list(stage1_hits.values())
    elif stage2_hits:
        df.at[idx, "Stage2_hit"] = list(stage2_hits.values())
    elif stage3_hits:
        df.at[idx, "Stage3_hit"] = list(stage3_hits.values())

    has_hit = bool(stage1_hits or stage2_hits or stage3_hits)
    if has_hit:
        df.at[idx, "matched"] = True
        df.at[idx, "matched_stage"] = (
            "stage1" if stage1_hits else "stage2" if stage2_hits else "stage3"
        )
    else:
        df.at[idx, "matched"] = False
        df.at[idx, "matched_stage"] = ""

    return {"hit": has_hit, "s1": s1, "s2": s2, "s3": s3, "s0": s0,
            "candidates": len(candidates)}


def process_excel(path: Path, overseas_map: dict, db: dict):
    print(f"processing: {path.name}")

    df = pd.read_excel(path, engine="openpyxl")
    judge_col = "judge" if "judge" in df.columns else "name_judge"
    if "edited_name" not in df.columns or judge_col not in df.columns:
        print("  Skipping: missing edited_name or judge")
        return None
    if "cc" not in df.columns:
        print("  Skipping: missing cc column")
        return None

    df["Stage1_hit"] = None
    df["Stage2_hit"] = None
    df["Stage3_hit"] = None
    df["matched"] = False
    df["matched_stage"] = ""

    not_target = df[judge_col].astype(str).str.strip() != "0"
    df.loc[not_target, "matched"] = True

    target_rows = df[df[judge_col].astype(str).str.strip() == "0"].index
    total_rows = len(target_rows)
    print(f"  judge==0 rows: {total_rows}")

    total_candidates = 0
    rows_with_hit = 0
    stage1_count = stage2_count = stage3_count = still_0_count = 0

    cc_groups = df.loc[target_rows].groupby("cc").groups
    for cc, group_idx in sorted(cc_groups.items()):
        cc_str = str(cc).strip()
        if not cc_str:
            continue
        print(f"    cc={cc_str}: {len(group_idx)} rows", flush=True)
        stage_maps = _build_stage_maps_for_cc(cc_str, overseas_map, db)

        for idx in group_idx:
            result = _match_row(idx, df, stage_maps)
            if result is None:
                continue
            total_candidates += result["candidates"]
            if result["hit"]:
                rows_with_hit += 1
            stage1_count += result["s1"]
            stage2_count += result["s2"]
            stage3_count += result["s3"]
            still_0_count += result["s0"]

    if total_candidates > 0:
        s1p = round(stage1_count / total_candidates * 100, 1)
        s2p = round(stage2_count / total_candidates * 100, 1)
        s3p = round(stage3_count / total_candidates * 100, 1)
        s0p = round(still_0_count / total_candidates * 100, 1)
    else:
        s1p = s2p = s3p = s0p = 0.0

    out_name = f"{path.stem}_result.xlsx"
    df.to_excel(OUTPUT_DIR / out_name, index=False)
    print(f"  saved: {out_name}")

    return {
        "file": path.stem,
        "total_0_target": total_rows,
        "rows_with_hit": rows_with_hit,
        "rows_still_0": total_rows - rows_with_hit,
        "total_candidates": total_candidates,
        "stage1": stage1_count, "stage1(%)": s1p,
        "stage2": stage2_count, "stage2(%)": s2p,
        "stage3": stage3_count, "stage3(%)": s3p,
        "still_0": still_0_count, "still_0(%)": s0p,
    }


def main():
    print("Loading geonames_master.pkl (once)...")
    db = load_master_pkl()
    print("Done.")

    overseas_map = load_overseas_map()
    stats = []

    for path in sorted(INPUT_DIR.glob("*.xlsx")):
        if is_excel_lock_file(path):
            continue
        s = process_excel(path, overseas_map, db)
        if s:
            stats.append(s)

    if stats:
        df_summary = pd.DataFrame(stats)
        df_summary.to_excel(OUTPUT_DIR / "tower2_world_summary.xlsx", index=False)
        print(f"tower2_world_summary.xlsx saved -> {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
