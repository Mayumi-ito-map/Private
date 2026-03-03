"""指定Excelファイルの列名を表示する _260301

使い方:
python scripts/prepare_excel/check_columns.py                    # デフォルト: cn129_FR_フランス_FRA.xlsx
python scripts/prepare_excel/check_columns.py cn002_AZ_xxx.xlsx # ファイル名を指定
python scripts/prepare_excel/check_columns.py --all              # 全ファイル
"""
import sys
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project/
INPUT_DIR = BASE_DIR / "excel_local_work"


def show_columns(file_path: Path) -> None:
    """1ファイルの列名を表示"""
    if not file_path.exists():
        print(f"ファイルが見つかりません: {file_path}")
        return
    df = pd.read_excel(file_path, nrows=0)  # ヘッダーのみ（高速）
    print(f"\n--- {file_path.name} ---")
    print(f"列数: {len(df.columns)}")
    for i, col in enumerate(df.columns, 1):
        print(f"  {i}. {col}")


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--all":
        for f in sorted(INPUT_DIR.glob("*.xlsx")):
            if not f.name.startswith("~"):  # ロックファイル除外
                show_columns(f)
    elif len(sys.argv) >= 2:
        file_path = INPUT_DIR / sys.argv[1]
        show_columns(file_path)
    else:
        file_path = INPUT_DIR / "*cn002_AZ_アゼルバイジャン_alternate.xlsx"
        show_columns(file_path)


if __name__ == "__main__":
    main()