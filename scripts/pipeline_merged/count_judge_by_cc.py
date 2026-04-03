"""
count_judge_by_cc.py

output_match_alternatenames_cate/*.xlsx (sheet: all) から、
cc（2桁国コード）ごとに judge 列の "1", "2+", "0" を集計し Excel 出力する。

出力: output_match_alternatenames_cate/judge_by_cc.xlsx
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

CATE_DIR = PROJECT_ROOT / "output_match_alternatenames_cate"
OUTPUT_PATH = CATE_DIR / "judge_by_cc.xlsx"

SKIP_FILES = {"judge_by_cc"}


def main():
    frames = []

    for path in sorted(CATE_DIR.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        if path.stem in SKIP_FILES:
            continue

        print(f"loading: {path.name}", flush=True)
        df = pd.read_excel(path, sheet_name="all", engine="openpyxl")

        if "cc" not in df.columns or "judge" not in df.columns:
            print(f"  skip: cc or judge column missing")
            continue

        # cn 列がない場合はファイル名の先頭（例: cn026, cn028）から補完
        if "cn" not in df.columns:
            cn_val = path.stem.split("_")[0] if "_" in path.stem else ""
            df["cn"] = cn_val
            print(f"  cn列なし → ファイル名から '{cn_val}' を補完")

        df["_judge"] = df["judge"].astype(str).str.strip()

        # cc ごとに cn の代表値を取得
        cc_cn = df.groupby("cc")["cn"].first().reset_index()

        # cc ごとに judge を集計
        total = df.groupby("cc").size().rename("total")
        j1 = df[df["_judge"] == "1"].groupby("cc").size().rename("judge_1")
        j2 = df[df["_judge"] == "2+"].groupby("cc").size().rename("judge_2+")
        j0 = df[df["_judge"] == "0"].groupby("cc").size().rename("judge_0")

        summary = pd.concat([total, j1, j2, j0], axis=1).fillna(0).astype(int)
        summary = summary.reset_index()
        summary = summary.merge(cc_cn, on="cc", how="left")
        summary["source_file"] = path.stem
        summary = summary[["source_file", "cn", "cc", "total", "judge_1", "judge_2+", "judge_0"]]

        frames.append(summary)

        print(f"  rows: {len(df):,}, cc count: {len(summary)}")

    if not frames:
        print("ERROR: no data")
        return

    df_all = pd.concat(frames, ignore_index=True)

    # 全体集計
    cc_cn_all = df_all.groupby("cc")["cn"].first().reset_index()
    grand = df_all.groupby("cc")[["total", "judge_1", "judge_2+", "judge_0"]].sum().reset_index()
    grand = grand.merge(cc_cn_all, on="cc", how="left")
    grand["source_file"] = "(全体)"
    grand = grand[["source_file", "cn", "cc", "total", "judge_1", "judge_2+", "judge_0"]]
    grand = grand.sort_values("cc")

    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        df_all.to_excel(writer, sheet_name="by_file", index=False)
        grand.to_excel(writer, sheet_name="grand_total", index=False)

    print(f"\n出力: {OUTPUT_PATH}")
    print(f"  by_file     : {len(df_all):,} 行（ファイル×cc の組み合わせ）")
    print(f"  grand_total : {len(grand):,} 行（cc ごとの全体集計）")

    total_all = grand["total"].sum()
    j1_all = grand["judge_1"].sum()
    j2_all = grand["judge_2+"].sum()
    j0_all = grand["judge_0"].sum()
    print(f"\n全体: {total_all:,} 行")
    print(f"  judge=1 : {j1_all:,} ({j1_all/total_all*100:.1f}%)")
    print(f"  judge=2+: {j2_all:,} ({j2_all/total_all*100:.1f}%)")
    print(f"  judge=0 : {j0_all:,} ({j0_all/total_all*100:.1f}%)")


if __name__ == "__main__":
    main()
