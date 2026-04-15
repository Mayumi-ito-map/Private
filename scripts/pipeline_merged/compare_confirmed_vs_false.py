"""
compare_confirmed_vs_false.py

0match/Confirmed_ID_260221.xlsx の index_ID 249件について、
output_match_results_work/*.xlsx の matched==FALSE の index_ID と照合し、
マッチする/しない を一覧にして Excel 出力する。

出力: 0match/confirmed_id_comparison.xlsx
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

CONFIRMED_PATH = PROJECT_ROOT / "0match" / "Confirmed_ID_260221.xlsx"
RESULTS_WORK_DIR = PROJECT_ROOT / "output_match_results_work"
OUTPUT_PATH = PROJECT_ROOT / "0match" / "confirmed_id_comparison.xlsx"

SKIP_FILES = {"tower2_world_summary", "matched_false_by_cc"}


def main():
    # ── 1. Confirmed_ID を読み込む ──
    print("=== Confirmed_ID_260221.xlsx ===", flush=True)
    df_confirmed = pd.read_excel(CONFIRMED_PATH, engine="openpyxl")
    df_confirmed["index_ID"] = df_confirmed["index_ID"].astype(str).str.strip()
    print(f"  行数: {len(df_confirmed):,}")
    print(f"  ユニーク index_ID: {df_confirmed['index_ID'].nunique():,}\n", flush=True)

    # ── 2. output_match_results_work から matched==FALSE の index_ID を収集 ──
    print("=== output_match_results_work/*.xlsx (matched==FALSE) ===", flush=True)
    false_ids = {}  # index_ID → source_file

    for path in sorted(RESULTS_WORK_DIR.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        if path.stem in SKIP_FILES:
            continue

        print(f"  loading: {path.name}", flush=True)
        df = pd.read_excel(path, engine="openpyxl")

        if "index_ID" not in df.columns or "matched" not in df.columns:
            print(f"    skip: index_ID or matched column missing")
            continue

        df["_matched_str"] = df["matched"].astype(str).str.strip().str.upper()
        df_false = df[df["_matched_str"] == "FALSE"]
        print(f"    rows: {len(df):,}, matched==FALSE: {len(df_false):,}")

        for _, row in df_false.iterrows():
            idx = str(row["index_ID"]).strip()
            false_ids[idx] = path.stem

    print(f"\n  matched==FALSE の合計ユニーク index_ID: {len(false_ids):,}\n", flush=True)

    # ── 3. 照合 ──
    print("=== 照合 ===", flush=True)

    df_confirmed["matched_FALSE_に存在"] = df_confirmed["index_ID"].isin(false_ids)
    df_confirmed["結果"] = df_confirmed["matched_FALSE_に存在"].map(
        {True: "一致あり", False: "一致なし"}
    )
    df_confirmed["FALSE_source_file"] = df_confirmed["index_ID"].map(false_ids).fillna("")

    n_match = df_confirmed["matched_FALSE_に存在"].sum()
    n_no_match = len(df_confirmed) - n_match
    print(f"  Confirmed 249件中:")
    print(f"    一致あり（matched=FALSE に存在）: {n_match:,}")
    print(f"    一致なし（matched=FALSE に不在）: {n_no_match:,}\n", flush=True)

    # ── 4. Excel 出力 ──
    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        df_confirmed.to_excel(writer, sheet_name="all", index=False)

        df_yes = df_confirmed[df_confirmed["matched_FALSE_に存在"] == True]
        if not df_yes.empty:
            df_yes.to_excel(writer, sheet_name="一致あり", index=False)

        df_no = df_confirmed[df_confirmed["matched_FALSE_に存在"] == False]
        if not df_no.empty:
            df_no.to_excel(writer, sheet_name="一致なし", index=False)

    print(f"出力: {OUTPUT_PATH}")
    print(f"  all     : {len(df_confirmed):,} 行（全件 + 結果列）")
    print(f"  一致あり: {n_match:,} 行")
    print(f"  一致なし: {n_no_match:,} 行")


if __name__ == "__main__":
    main()
