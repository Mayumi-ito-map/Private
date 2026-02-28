"""
utils.py

プロジェクト共通のユーティリティ関数。
"""

from pathlib import Path


def is_excel_lock_file(path: Path) -> bool:
    """
    Excel 編集中の一時ファイル（~$xxx.xlsx）を判定する。

    Args:
        path: ファイルパス（Path または path-like）

    Returns:
        True: ロックファイル（除外対象）
        False: 通常のファイル

    Examples:
        >>> is_excel_lock_file(Path("~$report.xlsx"))
        True
        >>> is_excel_lock_file(Path("report.xlsx"))
        False
    """
    return path.name.startswith("~$")
