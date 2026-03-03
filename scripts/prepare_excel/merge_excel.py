"""
Excel 合体スクリプト：使用列のみを取り出し、地域ごとに合体して正本データを作成

入力: excel_local_work/*.xlsx
出力: excel_local_merged/
  - cn300_北中アメリカ.xlsx
  - cn400_500_南米オセアニア.xlsx

採用列（21列）:
  index_ID, lat,long, GoogleMap, local_id, cc, cn, 大地図帳index, 大地図帳_欧文index,
  country, 堀江_表記修正, 堀江_欧文修正, 修正後和文地名, 修正後欧文地名,
  TIMES[13th], TIMES[16th], memo, 括弧情報, num, fcl, 国・地域名, alpha-2

使い方:
  python -m scripts.prepare_excel.merge_excel
"""
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = BASE_DIR / "excel_local_work"
OUTPUT_DIR = BASE_DIR / "excel_local_merged"

# 採用列（この順序で出力）
COLS = [
    "index_ID",
    "lat,long",
    "GoogleMap",
    "local_id",
    "cc",
    "cn",
    "大地図帳index",
    "大地図帳_欧文index",
    "country",
    "堀江_表記修正",
    "堀江_欧文修正",
    "修正後和文地名",
    "修正後欧文地名",
    "TIMES[13th]",
    "TIMES[16th]",
    "memo",
    "括弧情報",
    "num",
    "fcl",
    "国・地域名",
    "alpha-2",
]

# num → fcl 変換
NUM_TO_FCL = {
    (100, 199): "P",
    (200, 299): "A",
    (300, 399): "S",
    (400, 499): "H",
}

# 地域別: (出力ファイル名, 対象ファイルパターン)
REGIONS = [
    # ("cn300_北中アメリカ.xlsx", "cn3*.xlsx"),
    # ("cn400_500_南米オセアニア.xlsx", "cn4*.xlsx"),  # cn4 + cn5
    ("cn000_アジア.xlsx", "cn0*.xlsx"),
    ("cn100_ヨーロッパ.xlsx", "cn1*.xlsx"),
    ("cn200_アフリカ.xlsx", "cn2*.xlsx")
]


def parse_filename(path: Path) -> tuple[str, str]:
    """ファイル名から cn と cc を抽出"""
    parts = path.stem.split("_")
    cn = parts[0] if len(parts) >= 1 else ""
    cc = parts[1] if len(parts) >= 2 else ""
    return cn, cc


def num_to_fcl(num) -> str:
    """num の値を fcl に変換"""
    if pd.isna(num):
        return ""
    try:
        n = int(float(num))
    except (ValueError, TypeError):
        return ""
    for (lo, hi), fcl in NUM_TO_FCL.items():
        if lo <= n <= hi:
            return fcl
    return ""


def read_and_prepare(path: Path) -> pd.DataFrame | None:
    """1ファイルを読み、採用列のみに整えて返す"""
    cn, cc = parse_filename(path)
    if not cn or not cc:
        print(f"  skip (cn/cc 抽出不可): {path.name}")
        return None

    df = pd.read_excel(path)
    n_rows = len(df)

    # local_id, cc, cn, fcl がなければ追加
    if "local_id" not in df.columns:
        df["local_id"] = [f"{cc}{i:05d}" for i in range(1, n_rows + 1)]
    if "cc" not in df.columns:
        df["cc"] = cc
    if "cn" not in df.columns:
        df["cn"] = cn
    if "fcl" not in df.columns and "num" in df.columns:
        df["fcl"] = df["num"].apply(num_to_fcl)
    elif "fcl" not in df.columns:
        df["fcl"] = ""

    # 採用列のみ抽出（存在する列だけ）
    out_cols = []
    for c in COLS:
        if c in df.columns:
            out_cols.append(c)
        else:
            df[c] = ""
            out_cols.append(c)

    return df[out_cols]


def merge_region(pattern: str, out_name: str) -> int:
    """パターンに合うファイルを合体して出力"""
    if "cn4" in pattern:
        files = sorted(INPUT_DIR.glob("cn4*.xlsx")) + sorted(INPUT_DIR.glob("cn5*.xlsx"))
    else:
        files = sorted(INPUT_DIR.glob(pattern))

    files = [f for f in files if not f.name.startswith("~")]
    if not files:
        print(f"  対象ファイルなし: {pattern}")
        return 0

    dfs = []
    for path in files:
        d = read_and_prepare(path)
        if d is not None:
            dfs.append(d)
            print(f"  + {path.name} ({len(d)} 行)")

    if not dfs:
        print(f"  マージ対象なし: {pattern}")
        return 0

    merged = pd.concat(dfs, ignore_index=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / out_name
    merged.to_excel(out_path, index=False)
    print(f"  → {out_path.name} ({len(merged)} 行)")
    return len(merged)


def main():
    print("Excel 合体（cn300, cn400+cn500）")
    print(f"入力: {INPUT_DIR}")
    print(f"出力: {OUTPUT_DIR}\n")

    total = 0
    for out_name, pattern in REGIONS:
        print(f"--- {out_name} ---")
        n = merge_region(pattern, out_name)
        total += n
        print()

    print(f"完了: 合計 {total} 行")


if __name__ == "__main__":
    main()
