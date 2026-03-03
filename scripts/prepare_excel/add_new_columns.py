"""
各国毎の Excel に新規列（local_id, cc, cn, fcl）を追加する

入力: excel_local_work/*.xlsx
出力: excel_local_work_output/*_col.xlsx

新規列:
  1. local_id : 国コード + 5桁数字（例: FR00001）
  2. cc       : 国コード（ファイル名から抽出、例: FR）
  3. cn       : 国ファイル番号（例: cn129）
  4. fcl      : num を参照して変換（100-199→P, 200-299→A, 300-399→S, 400-499→T）

使い方:
  python scripts/prepare_excel/add_new_columns.py
"""
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = BASE_DIR / "excel_local_work"
OUTPUT_DIR = BASE_DIR / "excel_local_work_output"

# 保留（num 列なし等）: 処理対象外
SKIP_FILES = {
    "cn026_KR_韓国_KOR.xlsx",
    "cn028_CN_中国_CHN.xlsx",
    "cn029_KP_北朝鮮_PRK.xlsx",
}

# num → fcl 変換
NUM_TO_FCL = {
    (100, 199): "P",
    (200, 299): "A",
    (300, 399): "S",
    (400, 499): "T",
}


def parse_filename(path: Path) -> tuple[str, str]:
    """ファイル名から cn と cc を抽出
    例: cn129_FR_フランス_FRA.xlsx → ("cn129", "FR")
    """
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


def process_one(path: Path) -> bool:
    """1ファイルを処理し、出力する"""
    cn, cc = parse_filename(path)
    if not cn or not cc:
        print(f"  skip (cn/cc 抽出不可): {path.name}")
        return False

    df = pd.read_excel(path)

    n_rows = len(df)

    # 1. local_id : 国コード + 5桁数字
    local_ids = [f"{cc}{i:05d}" for i in range(1, n_rows + 1)]
    df["local_id"] = local_ids

    # 2. cc
    df["cc"] = cc

    # 3. cn
    df["cn"] = cn

    # 4. fcl : num を参照して変換
    if "num" in df.columns:
        df["fcl"] = df["num"].apply(num_to_fcl)
    else:
        df["fcl"] = ""
        print(f"  warn: num 列がありません: {path.name}")

    # 出力ファイル名: cn129_FR_フランス_FRA.xlsx → cn129_FR_フランス_FRA_col.xlsx
    out_name = path.stem + "_col.xlsx"
    out_path = OUTPUT_DIR / out_name

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_excel(out_path, index=False)
    print(f"  ok: {path.name} → {out_name} ({n_rows} 行)")
    return True


def main():
    excel_files = sorted(
        p for p in INPUT_DIR.glob("*.xlsx")
        if not p.name.startswith("~") and p.name not in SKIP_FILES
    )
    print(f"入力: {INPUT_DIR}")
    print(f"出力: {OUTPUT_DIR}")
    print(f"対象: {len(excel_files)} ファイル（保留: {len(SKIP_FILES)} 件）\n")

    ok_count = 0
    for path in excel_files:
        if process_one(path):
            ok_count += 1

    print(f"\n完了: {ok_count}/{len(excel_files)} ファイル")


if __name__ == "__main__":
    main()
