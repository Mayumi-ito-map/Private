"""
count_matched_false_by_cc.py

output_match_results/ の7つの Excel について、
cc 列の項目ごとに matched==FALSE の件数を集計し、一覧表 Excel を出力する。

出力: output_match_results/matched_false_by_cc.xlsx
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

RESULT_DIR = PROJECT_ROOT / "output_match_results"
OUTPUT_PATH = RESULT_DIR / "matched_false_by_cc.xlsx"

SKIP_FILES = {"tower2_world_summary", "matched_false_by_cc"}


def main():
    frames = []

    for path in sorted(RESULT_DIR.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue
        if path.stem in SKIP_FILES:
            continue

        print(f"loading: {path.name}", flush=True)
        df = pd.read_excel(path, engine="openpyxl")

        if "cc" not in df.columns or "matched" not in df.columns:
            print(f"  skip: cc or matched column missing")
            continue

        df["_matched_str"] = df["matched"].astype(str).str.strip().str.upper()
        df["_is_false"] = df["_matched_str"] == "FALSE"

        # cn 列がない場合はファイル名から補完
        if "cn" not in df.columns:
            stem = path.stem  # e.g. cn001_CN_asia_alternate_result
            cn_val = stem.split("_")[0] if "_" in stem else ""
            df["cn"] = cn_val

        # cc ごとに cn と local_id の代表値を取得
        agg_dict = {"cn": ("cn", "first")}
        if "local_id" in df.columns:
            agg_dict["local_id"] = ("local_id", "first")
        cc_info = df.groupby("cc").agg(**agg_dict).reset_index()
        if "local_id" not in cc_info.columns:
            cc_info["local_id"] = ""

        total_by_cc = df.groupby("cc").size().rename("total")
        false_by_cc = df[df["_is_false"]].groupby("cc").size().rename("matched_FALSE")

        summary = pd.concat([total_by_cc, false_by_cc], axis=1).fillna(0).astype(int)
        summary["matched_TRUE"] = summary["total"] - summary["matched_FALSE"]
        summary["FALSE_rate"] = (summary["matched_FALSE"] / summary["total"] * 100).round(1)
        summary = summary.reset_index()
        summary = summary.merge(cc_info, on="cc", how="left")
        summary["source_file"] = path.stem
        summary = summary[["source_file", "cn", "local_id", "cc", "total", "matched_TRUE", "matched_FALSE", "FALSE_rate"]]

        frames.append(summary)

        file_total = len(df)
        file_false = df["_is_false"].sum()
        print(f"  rows: {file_total:,}, matched==FALSE: {file_false:,}, cc count: {len(summary)}")

    if not frames:
        print("ERROR: no data")
        return

    df_all = pd.concat(frames, ignore_index=True)

    # 全体集計（cn, local_id は cc に対応する代表値を取得）
    cc_info_all = df_all.groupby("cc").agg(
        cn=("cn", "first"),
        local_id=("local_id", "first"),
    ).reset_index()

    grand = df_all.groupby("cc")[["total", "matched_TRUE", "matched_FALSE"]].sum().reset_index()
    grand["FALSE_rate"] = (grand["matched_FALSE"] / grand["total"] * 100).round(1)
    grand = grand.merge(cc_info_all, on="cc", how="left")
    grand["source_file"] = "(全体)"
    grand = grand[["source_file", "cn", "local_id", "cc", "total", "matched_TRUE", "matched_FALSE", "FALSE_rate"]]
    grand = grand.sort_values("matched_FALSE", ascending=False)

    with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:
        df_all.to_excel(writer, sheet_name="by_file", index=False)
        grand.to_excel(writer, sheet_name="grand_total", index=False)

    print(f"\n出力: {OUTPUT_PATH}")
    print(f"  by_file     : {len(df_all):,} 行（ファイル×cc の組み合わせ）")
    print(f"  grand_total : {len(grand):,} 行（cc ごとの全体集計）")

    # コンソールにも全体のサマリを表示
    total_all = grand["total"].sum()
    false_all = grand["matched_FALSE"].sum()
    print(f"\n全体: {total_all:,} 行中 matched==FALSE: {false_all:,} ({false_all/total_all*100:.1f}%)")


if __name__ == "__main__":
    main()
