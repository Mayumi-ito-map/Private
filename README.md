# GeoNames Matching Pipeline

GeoNames データを使って地名マッチングを行うパイプライン（v2 改良版）です。

## セットアップ

1. `.env.example` をコピーして `.env` を作成
2. 必要なパッケージをインストール

```bash
cp .env.example .env
pip install -r requirements.txt
```

## ディレクトリ構成

```
project/
├── normalizers/          # 正規化処理
├── scripts/
│   ├── pipeline_merged/  # メインパイプライン
│   ├── prepare_excel/    # Excel前処理
│   └── geojson/          # GeoJSON分割ツール
├── config/               # 設定ファイル
└── data/                 # データファイル
```

## 使い方

### 地名マッチングの実行

```bash
python scripts/pipeline_merged/run_local_build.py
```

### GeoJSON の国別分割

```bash
python scripts/geojson/split_geojson_by_country.py
```
