"""TIMES[13th] または TIMES[16th] にデータが入っているファイル名を表示する

使い方:
  python scripts/prepare_excel/list_times_columns.py
"""
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = BASE_DIR / "excel_local_work"

COLS = ["TIMES[13th]", "TIMES[16th]"]


def has_data(series: pd.Series) -> bool:
    """Series に有効なデータが1件以上あるか"""
    for v in series:
        if pd.notna(v) and str(v).strip():
            return True
    return False


def main():
    excel_files = sorted(p for p in INPUT_DIR.glob("*.xlsx") if not p.name.startswith("~"))
    print(f"対象: {len(excel_files)} ファイル\n")

    found = []
    for path in excel_files:
        df = pd.read_excel(path)
        for col in COLS:
            if col in df.columns and has_data(df[col]):
                found.append(path.name)
                break

    print(f"TIMES[13th] または TIMES[16th] にデータがあるファイル: {len(found)} 件\n")
    for name in found:
        print(name)


if __name__ == "__main__":
    main()
