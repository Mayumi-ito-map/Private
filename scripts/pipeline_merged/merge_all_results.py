"""
merge_all_results.py — 全マッチング結果の統合

5つのデータソースを index_id で結合し、統合 Excel を生成する。

【本流】
  ① 司令塔①（カテゴリ＋閾値フィルタあり）: output_match_alternatenames_cate/*.xlsx
  ③ 司令塔②（あいまいマッチング）: output_match_results/*.xlsx

【補完】
  ② Google API マッチング: output_google_api_match/*.xlsx
  ④ 全世界マッチング: output_match_worldwide_distance/*.xlsx
  ⑤ フィルタなしマッチング: output_match_alternatenames_base/*.xlsx

出力: output_merged/merged_all.xlsx
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

# =========================================================
# パス設定
# =========================================================
BASE_DIR = PROJECT_ROOT

# 本流
LOCAL_CATE_DIR = BASE_DIR / "output_match_alternatenames_cate"
STAGE_DIR = BASE_DIR / "output_match_results"

# 補完
GA_DIR = BASE_DIR / "output_google_api_match"
WORLDWIDE_DIR = BASE_DIR / "output_match_worldwide_distance"
LOCAL_BASE_DIR = BASE_DIR / "output_match_alternatenames_base"

# 出力
OUTPUT_DIR = BASE_DIR / "output_merged"

# =========================================================
# index_id の列名候補（Excel 側は index_ID の場合もある）
# =========================================================
INDEX_ID_CANDIDATES = ["index_id", "index_ID", "INDEX_ID"]


def _find_index_col(df: pd.DataFrame) -> str | None:
    for c in INDEX_ID_CANDIDATES:
        if c in df.columns:
            return c
    return None


def _normalize_index_id(df: pd.DataFrame) -> pd.DataFrame:
    """index_id 列を統一名 'index_id' に正規化する。"""
    col = _find_index_col(df)
    if col is None:
        return df
    if col != "index_id":
        df = df.rename(columns={col: "index_id"})
    df["index_id"] = df["index_id"].astype(str).str.strip()
    return df


def _is_lock_file(path: Path) -> bool:
    return path.name.startswith("~$")


def _dedup_by_index_id(df: pd.DataFrame, judge_col: str, label: str) -> pd.DataFrame:
    """
    index_id の重複を排除する。
    同一 index_id が複数行ある場合の優先順位:
      1. judge == "1"（1件確定 — 最優先）
      2. judge == "2+"（複数マッチ）
      3. judge == "0" またはその他
    """
    if "index_id" not in df.columns or df.empty:
        return df

    before = len(df)
    n_unique = df["index_id"].nunique()
    n_dup = before - n_unique

    if n_dup == 0:
        return df

    if judge_col and judge_col in df.columns:
        j = df[judge_col].astype(str).str.strip()
        df["_sort_priority"] = j.map({"1": 0, "2+": 1}).fillna(2).astype(int)
        # TRUE → 0（最優先） に変換
        if judge_col in ("stage_matched",):
            is_true = j.str.upper().isin(("TRUE", "1"))
            df["_sort_priority"] = (~is_true).astype(int)
        df = df.sort_values("_sort_priority", ascending=True)
        df = df.drop_duplicates(subset="index_id", keep="first")
        df = df.drop(columns="_sort_priority")
    else:
        df = df.drop_duplicates(subset="index_id", keep="first")

    print(f"  ⚠ {label}: 重複 {n_dup:,} 行を排除 ({before:,} → {len(df):,})", flush=True)
    return df


# =========================================================
# 1. 司令塔①（カテゴリフィルタあり）の読み込み
# =========================================================
def load_local_cate() -> pd.DataFrame:
    """司令塔①のカテゴリフィルタあり結果をベースデータとして読み込む。"""
    print("=== ① 司令塔①（カテゴリフィルタあり）===")
    frames = []
    if not LOCAL_CATE_DIR.exists():
        print(f"  WARNING: {LOCAL_CATE_DIR} が存在しません")
        return pd.DataFrame()

    for path in sorted(LOCAL_CATE_DIR.glob("*.xlsx")):
        if _is_lock_file(path):
            continue
        print(f"  loading: {path.name}", flush=True)
        df = pd.read_excel(path, sheet_name="all", engine="openpyxl")
        df["_source_file"] = path.stem
        frames.append(df)

    if not frames:
        print("  WARNING: Excel ファイルが見つかりません")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df = _normalize_index_id(df)
    df = _dedup_by_index_id(df, "judge", "司令塔①")
    print(f"  合計: {len(df):,} 行（ユニーク index_id: {df['index_id'].nunique():,}）\n", flush=True)
    return df


# =========================================================
# 2. 司令塔②（あいまいマッチング）の読み込み
# =========================================================
STAGE_KEEP_COLS = [
    "Stage1_hit", "Stage2_hit", "Stage3_hit",
    "matched", "matched_stage",
]

STAGE_RENAME = {
    "matched": "stage_matched",
    "matched_stage": "stage_matched_stage",
}


def load_stage_results() -> pd.DataFrame:
    """司令塔②の結果から Stage 列のみ抽出。"""
    print("=== ③ 司令塔②（あいまいマッチング）===")
    frames = []
    if not STAGE_DIR.exists():
        print(f"  WARNING: {STAGE_DIR} が存在しません")
        return pd.DataFrame()

    for path in sorted(STAGE_DIR.glob("*.xlsx")):
        if _is_lock_file(path):
            continue
        if path.stem == "tower2_world_summary":
            continue
        print(f"  loading: {path.name}", flush=True)
        df = pd.read_excel(path, engine="openpyxl")
        df = _normalize_index_id(df)
        frames.append(df)

    if not frames:
        print("  WARNING: Excel ファイルが見つかりません")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    keep = ["index_id"] + [c for c in STAGE_KEEP_COLS if c in df.columns]
    df = df[keep].copy()
    df = df.rename(columns=STAGE_RENAME)
    df = _dedup_by_index_id(df, "stage_matched", "司令塔②")
    print(f"  合計: {len(df):,} 行\n", flush=True)
    return df


# =========================================================
# 3. Google API マッチングの読み込み
# =========================================================
GA_KEEP_COLS = [
    "ga_judge", "ga_matched_stage", "ga_matched",
    "ga_matched_geonameid", "ga_matched_gn_name",
    "google_api_name", "source_type", "comparison",
]


def load_google_api() -> pd.DataFrame:
    """Google API マッチングの結果。"""
    print("=== ② Google API マッチング ===")
    frames = []
    if not GA_DIR.exists():
        print(f"  WARNING: {GA_DIR} が存在しません")
        return pd.DataFrame()

    for path in sorted(GA_DIR.glob("*.xlsx")):
        if _is_lock_file(path):
            continue
        print(f"  loading: {path.name}", flush=True)
        df = pd.read_excel(path, sheet_name="all", engine="openpyxl")
        df = _normalize_index_id(df)
        frames.append(df)

    if not frames:
        print("  WARNING: Excel ファイルが見つかりません")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    keep = ["index_id"] + [c for c in GA_KEEP_COLS if c in df.columns]
    df = df[keep].copy()
    df = _dedup_by_index_id(df, "ga_judge", "Google API")
    print(f"  合計: {len(df):,} 行\n", flush=True)
    return df


# =========================================================
# 4. 全世界マッチングの読み込み
# =========================================================
WW_KEEP_COLS = ["judge", "matched_stage", "matched", "matched_geonameid"]
WW_RENAME = {
    "judge": "ww_judge",
    "matched_stage": "ww_matched_stage",
    "matched": "ww_matched",
    "matched_geonameid": "ww_geonameid",
}


def load_worldwide() -> pd.DataFrame:
    """全世界マッチングの結果。"""
    print("=== ④ 全世界マッチング ===")
    frames = []
    if not WORLDWIDE_DIR.exists():
        print(f"  WARNING: {WORLDWIDE_DIR} が存在しません")
        return pd.DataFrame()

    for path in sorted(WORLDWIDE_DIR.glob("*.xlsx")):
        if _is_lock_file(path):
            continue
        print(f"  loading: {path.name}", flush=True)
        df = pd.read_excel(path, engine="openpyxl")
        df = _normalize_index_id(df)
        frames.append(df)

    if not frames:
        print("  WARNING: Excel ファイルが見つかりません")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    keep = ["index_id"] + [c for c in WW_KEEP_COLS if c in df.columns]
    df = df[keep].copy()
    df = df.rename(columns=WW_RENAME)
    df = _dedup_by_index_id(df, "ww_judge", "全世界")
    print(f"  合計: {len(df):,} 行\n", flush=True)
    return df


# =========================================================
# 5. フィルタなしマッチングの読み込み
# =========================================================
BASE_KEEP_COLS = ["judge", "matched_stage", "matched", "matched_geonameid"]
BASE_RENAME = {
    "judge": "base_judge",
    "matched_stage": "base_matched_stage",
    "matched": "base_matched",
    "matched_geonameid": "base_geonameid",
}


def load_local_base() -> pd.DataFrame:
    """フィルタなしマッチングの結果。"""
    print("=== ⑤ フィルタなしマッチング ===")
    frames = []
    if not LOCAL_BASE_DIR.exists():
        print(f"  WARNING: {LOCAL_BASE_DIR} が存在しません")
        return pd.DataFrame()

    for path in sorted(LOCAL_BASE_DIR.glob("*.xlsx")):
        if _is_lock_file(path):
            continue
        print(f"  loading: {path.name}", flush=True)
        df = pd.read_excel(path, sheet_name="all", engine="openpyxl")
        df = _normalize_index_id(df)
        frames.append(df)

    if not frames:
        print("  WARNING: Excel ファイルが見つかりません")
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    keep = ["index_id"] + [c for c in BASE_KEEP_COLS if c in df.columns]
    df = df[keep].copy()
    df = df.rename(columns=BASE_RENAME)
    df = _dedup_by_index_id(df, "base_judge", "フィルタなし")
    print(f"  合計: {len(df):,} 行\n", flush=True)
    return df


# =========================================================
# final_status の算出
# =========================================================
def compute_final_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    本流（司令塔①②）の結果で final_status を決定。
    補完データ（ww / base / ga）はフラグとして付与。
    """
    df = df.copy()

    def _status(row):
        local_j = str(row.get("judge", "0")).strip()
        stage_matched = row.get("stage_matched", False)
        stage_stage = str(row.get("stage_matched_stage", "")).strip()

        # 本流: 司令塔①で hit
        if local_j in ("1", "2+"):
            return f"hit-{local_j}"

        # 本流: 司令塔②で hit
        if stage_matched is True or str(stage_matched).strip().upper() == "TRUE":
            return f"hit-{stage_stage}"

        return "zero"

    df["final_status"] = df.apply(_status, axis=1)

    # 補完フラグ: zero の中で補完データにヒットがあるか
    def _supplement(row):
        if row["final_status"] != "zero":
            return ""
        flags = []
        ww_j = str(row.get("ww_judge", "0")).strip()
        base_j = str(row.get("base_judge", "0")).strip()
        ga_j = str(row.get("ga_judge", "0")).strip()

        if ww_j in ("1", "2+"):
            flags.append(f"ww={ww_j}")
        if base_j in ("1", "2+"):
            flags.append(f"base={base_j}")
        if ga_j in ("1", "2+"):
            flags.append(f"ga={ga_j}")

        return " / ".join(flags) if flags else ""

    df["supplement_flags"] = df.apply(_supplement, axis=1)

    return df


# =========================================================
# 集計
# =========================================================
def build_summary(df: pd.DataFrame) -> pd.DataFrame:
    """final_status の集計表を作成。"""
    rows = []

    total = len(df)
    hit1 = (df["final_status"] == "hit-1").sum()
    hit2 = (df["final_status"] == "hit-2+").sum()
    stage1 = (df["final_status"] == "hit-stage1").sum()
    stage2 = (df["final_status"] == "hit-stage2").sum()
    stage3 = (df["final_status"] == "hit-stage3").sum()
    zero_total = (df["final_status"] == "zero").sum()
    zero_with_supp = ((df["final_status"] == "zero") & (df["supplement_flags"] != "")).sum()
    zero_pure = zero_total - zero_with_supp

    rows.append(("全件数", total, f"{100.0:.1f}%"))
    rows.append(("", "", ""))
    rows.append(("【本流】", "", ""))
    rows.append(("  hit-1（司令塔①で1件確定）", hit1, f"{hit1/total*100:.1f}%"))
    rows.append(("  hit-2+（司令塔①で複数マッチ）", hit2, f"{hit2/total*100:.1f}%"))
    rows.append(("  hit-stage1（司令塔②Stage1）", stage1, f"{stage1/total*100:.1f}%"))
    rows.append(("  hit-stage2（司令塔②Stage2）", stage2, f"{stage2/total*100:.1f}%"))
    rows.append(("  hit-stage3（司令塔②Stage3）", stage3, f"{stage3/total*100:.1f}%"))
    rows.append(("", "", ""))
    rows.append(("【0マッチ】", "", ""))
    rows.append(("  zero（補完あり）", zero_with_supp, f"{zero_with_supp/total*100:.1f}%"))
    rows.append(("  zero（完全不明）", zero_pure, f"{zero_pure/total*100:.1f}%"))
    rows.append(("  zero（計）", zero_total, f"{zero_total/total*100:.1f}%"))

    # 補完フラグの内訳
    if zero_with_supp > 0:
        rows.append(("", "", ""))
        rows.append(("【zero（補完あり）の内訳】", "", ""))
        zero_df = df[(df["final_status"] == "zero") & (df["supplement_flags"] != "")]

        has_ww = zero_df["supplement_flags"].str.contains("ww=").sum()
        has_base = zero_df["supplement_flags"].str.contains("base=").sum()
        has_ga = zero_df["supplement_flags"].str.contains("ga=").sum()

        rows.append(("  全世界マッチングでヒットあり", has_ww, ""))
        rows.append(("  フィルタなしでヒットあり", has_base, ""))
        rows.append(("  Google APIでヒットあり", has_ga, ""))

    return pd.DataFrame(rows, columns=["項目", "件数", "割合"])


# =========================================================
# メイン
# =========================================================
def main():
    print("=" * 60)
    print("  地名マッチング統合スクリプト")
    print("=" * 60)
    print(flush=True)

    # ── 1. ベースデータ（司令塔①カテゴリフィルタあり）──
    df_base = load_local_cate()
    if df_base.empty:
        print("ERROR: ベースデータが読み込めません。終了します。")
        return

    idx_col = _find_index_col(df_base)
    if idx_col is None:
        print("WARNING: index_id 列が見つかりません。行番号で結合します。")
        df_base["index_id"] = df_base.index.astype(str)

    print(f"結合キー: index_id ({df_base['index_id'].nunique():,} ユニーク値)\n")

    # ── 2. 各データソースの読み込み ──
    df_stage = load_stage_results()
    df_ga = load_google_api()
    df_ww = load_worldwide()
    df_local_base = load_local_base()

    # ── 3. 結合 ──
    print("=== 結合処理 ===")
    df = df_base.copy()

    if not df_stage.empty and "index_id" in df_stage.columns:
        df = df.merge(df_stage, on="index_id", how="left", suffixes=("", "_stg"))
        print(f"  司令塔② を結合: {len(df_stage):,} 行")

    if not df_ga.empty and "index_id" in df_ga.columns:
        df = df.merge(df_ga, on="index_id", how="left", suffixes=("", "_ga"))
        print(f"  Google API を結合: {len(df_ga):,} 行")

    if not df_ww.empty and "index_id" in df_ww.columns:
        df = df.merge(df_ww, on="index_id", how="left", suffixes=("", "_ww"))
        print(f"  全世界マッチング を結合: {len(df_ww):,} 行")

    if not df_local_base.empty and "index_id" in df_local_base.columns:
        df = df.merge(df_local_base, on="index_id", how="left", suffixes=("", "_base"))
        print(f"  フィルタなし を結合: {len(df_local_base):,} 行")

    base_count = len(df_base)
    if len(df) != base_count:
        print(f"\n  ⚠ 行数変化: ベース {base_count:,} → 統合後 {len(df):,}（差分 {len(df) - base_count:+,}）")
        print(f"    → 重複 index_id が残っている可能性があります")
    print(f"\n  統合後: {len(df):,} 行（ベースと同数であること: {'OK' if len(df) == base_count else 'NG'}）\n", flush=True)

    # ── 4. final_status 算出 ──
    print("=== final_status 算出 ===")
    df = compute_final_status(df)

    status_counts = df["final_status"].value_counts()
    for s, c in status_counts.items():
        print(f"  {s}: {c:,}")
    print(flush=True)

    # ── 5. 集計表 ──
    df_summary = build_summary(df)

    # ── 6. 出力 ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "merged_all.xlsx"
    print(f"=== Excel 出力: {out_path} ===")

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # Sheet1: 集計表
        df_summary.to_excel(writer, sheet_name="summary", index=False)

        # all: 全行
        df.to_excel(writer, sheet_name="all", index=False)

        # hit-1: 本流で1件確定
        df_hit1 = df[df["final_status"] == "hit-1"]
        if not df_hit1.empty:
            df_hit1.to_excel(writer, sheet_name="hit-1", index=False)

        # hit-2+: 本流で複数マッチ
        df_hit2 = df[df["final_status"] == "hit-2+"]
        if not df_hit2.empty:
            df_hit2.to_excel(writer, sheet_name="hit-2+", index=False)

        # stage: 司令塔②でヒット
        df_stage_hit = df[df["final_status"].str.startswith("hit-stage")]
        if not df_stage_hit.empty:
            df_stage_hit.to_excel(writer, sheet_name="stage_hit", index=False)

        # zero_supplement: 0マッチだが補完あり
        df_zero_supp = df[
            (df["final_status"] == "zero") & (df["supplement_flags"] != "")
        ]
        if not df_zero_supp.empty:
            df_zero_supp.to_excel(writer, sheet_name="zero_supplement", index=False)

        # zero_unknown: 完全不明
        df_zero_unk = df[
            (df["final_status"] == "zero") & (df["supplement_flags"] == "")
        ]
        if not df_zero_unk.empty:
            df_zero_unk.to_excel(writer, sheet_name="zero_unknown", index=False)

    print(f"  done. ({len(df):,} 行)")
    print(f"\nシート構成:")
    print(f"  summary       : 集計表")
    print(f"  all            : 全行データ ({len(df):,})")
    print(f"  hit-1          : 司令塔①で1件確定 ({len(df_hit1):,})")
    print(f"  hit-2+         : 司令塔①で複数マッチ ({len(df_hit2):,})")
    print(f"  stage_hit      : 司令塔②でヒット ({len(df_stage_hit):,})")
    print(f"  zero_supplement: 0マッチ（補完あり）({len(df_zero_supp):,})")
    print(f"  zero_unknown   : 完全不明 ({len(df_zero_unk):,})")


if __name__ == "__main__":
    main()
