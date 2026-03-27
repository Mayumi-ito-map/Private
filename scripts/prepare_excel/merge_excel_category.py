# 複数Excelのマージ

import pandas as pd
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent 

INPUT_DIR = BASE_DIR / "output_match_name_work"
main_path = BASE_DIR / "output_match_name_work"
main = pd.read_excel(main_path, dtype={'local_id': str})

# order = [
#     "cn450_oceania_name_P&P.xlsx",
#     "cn450_oceania_name_A&L.xlsx",
#     "cn450_oceania_name_S&L.xlsx",
#     "cn450_oceania_name_T&H.xlsx",
# ]

order = [
    "cn000_asia_alternate_P&P.xlsx",
    "cn000_asia_alternate_A&L.xlsx",
    "cn000_asia_alternate_S&L.xlsx",
    "cn000_asia_alternate_T&H.xlsx",
]

# 必要列辞書
# cols = {
#     "P&P": ["local_id", "PP-hit-name-1", "PP-name-1", "PP-name-2"],
#     "A&L": ["local_id", "AL-hit-name-1", "AL-name-1", "AL-name-2"],
#     "S&L": ["local_id", "SL-hit-name-1", "SL-name-1", "SL-name-2"],
#     "T&H": ["local_id", "TH-hit-name-1", "TH-name-1", "TH-name-2"],
# }

cols = {
    "P&P": ["local_id", "PP-hit-alter-1", "PP-alter-1", "PP-alter-2"],
    "A&L": ["local_id", "AL-hit-alter-1", "AL-alter-1", "AL-alter-2"],
    "S&L": ["local_id", "SL-hit-alter-1", "SL-alter-1", "SL-alter-2"],
    "T&H": ["local_id", "TH-hit-alter-1", "TH-alter-1", "TH-alter-2"],
}

df = main.copy()
for file_name in order:
    file_path = BASE_DIR / file_name
    key = file_name.replace(".xlsx", "").split("_")[-1]  # 最後の部分（P&P, A&L等）を抽出
    sub_cols = cols[key]
    # 既存の重複列を削除（merge時に _x/_y が付くのを防ぐ）
    drop_cols = [c for c in sub_cols if c != "local_id" and c in df.columns]
    df = df.drop(columns=drop_cols, errors="ignore")
    sub = pd.read_excel(file_path, dtype={'local_id': str})[sub_cols]
    df = df.merge(sub, on="local_id", how="left")

df = df.fillna("")  # NaNを空文字に置換

out_path = BASE_DIR / "cn000_asia_w_alternate_work01.xlsx"
df.to_excel(out_path, index=False)

print("マージが完了しました。")