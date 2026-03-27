"""
全世界マッチング結果のフラグを tower1_world_stats にマージする。

入力:
  - output_match_worldwide/*.xlsx（5ファイルを結合）
  - output_match/tower1_world_stats_cate_exclude_dis07_work.xlsx, sheet: all

処理:
  - local_id をキーにマージ
  - name_judge が "2+" または "1" の行 → name_ww にフラグ（2+ or 1）
  - alter_judge が "2+" または "1" の行 → alter_ww にフラグ（2+ or 1）
  - worldwide に存在しない local_id は name_ww, alter_ww を空欄

出力:
  - output_match/tower1_world_stats_cate_exclude_dis07_work_merge.xlsx
  - 既存 sheet をそのまま残し、all に name_ww, alter_ww を追加

使い方:
  python -m scripts.pipeline_merged.merge_worldwide_flags
"""

import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORLDWIDE_DIR = PROJECT_ROOT / "output_match_worldwide"
OUTPUT_DIR = PROJECT_ROOT / "output_match"
TOWER1_INPUT = OUTPUT_DIR / "tower1_world_stats_cate_exclude_dis07_work.xlsx"
TOWER1_OUTPUT = OUTPUT_DIR / "tower1_world_stats_cate_exclude_dis07_work_merge.xlsx"

# 全世界モードの出力ファイルパターン（run_local_build の MERGED_PATTERNS に対応）
WORLDWIDE_PATTERNS = [
    "cn000_asia_terrain_phase1_2.xlsx",
    "cn100_europe_terrain_phase1_2.xlsx",
    "cn200_africa_terrain_phase1_2.xlsx",
    "cn300_america_terrain_phase1_2.xlsx",
    "cn450_oceania_terrain_phase1_2.xlsx",
]


def load_worldwide_combined() -> pd.DataFrame:
    """5つの worldwide ファイルを結合。local_id 重複時は最初を採用。"""
    dfs = []
    for name in WORLDWIDE_PATTERNS:
        path = WORLDWIDE_DIR / name
        if not path.exists():
            print(f"  skip (not found): {path.name}")
            continue
        df = pd.read_excel(path, dtype={"local_id": str})
        dfs.append(df)
        print(f"  load: {path.name} ({len(df)} 行)")

    if not dfs:
        return pd.DataFrame()

    combined = pd.concat(dfs, ignore_index=True)
    # local_id 重複時は最初にマッチした行を採用
    combined = combined.drop_duplicates(subset=["local_id"], keep="first")
    print(f"  結合後: {len(combined)} 行（重複除去後）")
    return combined


def build_ww_flags(df_ww: pd.DataFrame) -> pd.DataFrame:
    """
    name_judge, alter_judge から name_ww, alter_ww を生成。
    対象は "2+", "1" のみ。それ以外は空欄。
    """
    df = df_ww[["local_id"]].copy()

    def _flag(val, allowed):
        if pd.isna(val):
            return ""
        s = str(val).strip()
        return s if s in allowed else ""

    df["name_ww"] = df_ww["name_judge"].apply(
        lambda x: _flag(x, ("2+", "1"))
    )
    df["alter_ww"] = df_ww["alter_judge"].apply(
        lambda x: _flag(x, ("2+", "1"))
    )
    return df


def main():
    print("=== 全世界マッチングフラグのマージ ===\n")

    if not TOWER1_INPUT.exists():
        print(f"エラー: 入力ファイルが見つかりません: {TOWER1_INPUT}")
        return

    print("1. worldwide ファイルの読込")
    df_ww = load_worldwide_combined()
    if len(df_ww) == 0:
        print("エラー: worldwide ファイルが1件も読み込めませんでした。")
        return

    if "local_id" not in df_ww.columns:
        print("エラー: worldwide に local_id 列がありません。")
        return
    if "name_judge" not in df_ww.columns or "alter_judge" not in df_ww.columns:
        print("エラー: worldwide に name_judge または alter_judge 列がありません。")
        return

    print("\n2. フラグ列の生成 (name_ww, alter_ww)")
    df_flags = build_ww_flags(df_ww)
    n_name = (df_flags["name_ww"] != "").sum()
    n_alter = (df_flags["alter_ww"] != "").sum()
    print(f"  name_ww フラグあり: {n_name} 件")
    print(f"  alter_ww フラグあり: {n_alter} 件")

    print("\n3. tower1 の読込")
    xl = pd.ExcelFile(TOWER1_INPUT)
    sheet_names = xl.sheet_names
    print(f"  sheets: {sheet_names}")

    if "all" not in sheet_names:
        print("エラー: 'all' シートがありません。")
        return

    df_all = pd.read_excel(TOWER1_INPUT, sheet_name="all", dtype={"local_id": str})
    if "local_id" not in df_all.columns:
        print("エラー: tower1 all に local_id 列がありません。")
        return

    print(f"  all: {len(df_all)} 行")

    print("\n4. マージ（local_id をキーに left join）")
    # 既存の name_ww, alter_ww があれば削除してからマージ
    df_all = df_all.drop(columns=["name_ww", "alter_ww"], errors="ignore")
    df_merged = df_all.merge(
        df_flags[["local_id", "name_ww", "alter_ww"]],
        on="local_id",
        how="left",
    )
    # worldwide に存在しない local_id は NaN → 空欄
    df_merged["name_ww"] = df_merged["name_ww"].fillna("")
    df_merged["alter_ww"] = df_merged["alter_ww"].fillna("")

    print("\n5. 出力")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(TOWER1_OUTPUT, engine="openpyxl") as writer:
        for sheet in sheet_names:
            if sheet == "all":
                df_merged.to_excel(writer, sheet_name=sheet, index=False)
            else:
                pd.read_excel(TOWER1_INPUT, sheet_name=sheet).to_excel(
                    writer, sheet_name=sheet, index=False
                )
    print(f"  -> {TOWER1_OUTPUT}")
    print("\nDone.")


if __name__ == "__main__":
    main()
