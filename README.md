# GeoNames Matching Pipeline

GeoNames データを使って地名マッチングを行うパイプラインです。

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
