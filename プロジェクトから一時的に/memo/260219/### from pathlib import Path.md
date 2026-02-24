###  from pathlib import Path

これ全部消してOK：
```
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
```
正しい書き方
```
from pathlib import Path
import json
import pandas as pd

# 正規化エンジン
from matchers.stage_matcher import (
    normalize_stage1,
    normalize_stage2,
    normalize_stage3,
)

BASE_DIR = Path(__file__).resolve().parent

INPUT_DIR = BASE_DIR / "output_match"
JSON_DIR = BASE_DIR / "output_json"
OUTPUT_DIR = BASE_DIR / "output_match_results"
CONFIG_DIR = BASE_DIR / "config"

OVERSEAS_FILE = CONFIG_DIR / "overseas_territories.json"

OUTPUT_DIR.mkdir(exist_ok=True)

```

ぜ今は不要なのか
Pythonは
「実行したファイルがあるディレクトリ」
を自動で sys.path に入れる。

python run_stage_match.py
と project/ で実行すれば、
project/
が検索対象になる。だから、
matchers/
は普通に import できる。

sys.path が必要になるのは？
scripts/ フォルダの中に司令塔を置いたとき
親ディレクトリのモジュールを読みに行くとき

project_new/
├── normalizers/
├── matchers/
├── config/
├── output_match/
├── output_match_results/
├── output_json/
├── run_build_local.py
├── run_stage_match.py


---

###  __init.py__ は自動?
自分で作る。中身は空でOK


from normalizers.normalize_comma_abb import normalize_comma_abb
この normalizers を「パッケージ」として認識させるために
__init__.py がある。

Python3.3以降は「暗黙の名前空間パッケージ」があるから
理論上は動く場合もある。

* 環境によって挙動変わる
* パッケージとして明示したほうが安全
* チーム開発では必須レベル

置く場所	意味
normalizers/init.py	必須（パッケージ化）
matchers/init.py	必須
project_new/init.py	今は不要


project_new/
    normalizers/
    matchers/
    run_build_local.py
なら、
python run_build_local.py
で実行する。

---
__init__.pyを作ったら、スクリプトも一部修正しますか？

今の import 書き方のままなら、修正いらない。
```
from normalizers.normalize_comma_abb import normalize_comma_abb
from matchers.stage_matcher import normalize_stage1
```
この形なら、
normalizers/__init__.py
matchers/__init__.py
を置くだけでOK。

スクリプト側は変更不要。

---
project_new/
│
├── normalizers/
│   ├── __init__.py   ← 空でOK
│   ├── normalize_comma_abb.py
│
├── matchers/
│   ├── __init__.py   ← 空でOK
│   ├── stage_matcher.py

---
**中身は空でいい。**

なんで必要？

__init__.py があると
Pythonが
「このフォルダはパッケージです」
って認識する。
だから、
from normalizers.normalize_comma_abb import normalize_comma_abb
が動く。

コマンドで作るならば、
```
touch normalizers/__init__.py
touch matchers/__init__.py
```

今のあなたの構成なら
__init__.py入れたら sys.path はいらない。