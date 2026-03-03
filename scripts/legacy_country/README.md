# legacy_country

国毎の Excel ファイルを入力とする旧パイプライン（比較・検証用）

## 概要

このフォルダには、世界大地図帳データベース作成プロジェクトの**国毎**の Excel を処理するスクリプトが格納されています。合体 Excel 用の新パイプライン（`scripts/pipeline_merged/`）に移行したため、比較・検証用として残しています。

## 含まれるスクリプト

| ファイル | 役割 |
|----------|------|
| `run_local_build.py` | 司令塔①：国毎 Excel から GeoNames マッチング（name / alternatenames） |
| `run_stage_match.py` | 司令塔②：judge==0 の行を Stage1→2→3 でマッチング |
| `export_for_leaflet.py` | Leaflet 地図用 GeoJSON 出力 |

## 入力・出力

- **入力**: `excel_local/*.xlsx`（国毎の Excel、例: cn002_AZ_アゼルバイジャン_AZE.xlsx）
- **出力**: `output_match/`, `output_match_name/`, `output_match_alternatenames/`, `output_match_results/`

## 実行方法

プロジェクトルートで以下を実行してください。

```bash
# 司令塔①
python scripts/legacy_country/run_local_build.py

# 司令塔②
python scripts/legacy_country/run_stage_match.py

# Leaflet 用 GeoJSON 出力
python scripts/legacy_country/export_for_leaflet.py
```

※ `geonames_loader`, `normalizers`, `utils` 等はプロジェクトルートのモジュールを参照します。プロジェクトルートで実行する必要があります。

## 注意

- これらのスクリプトは `BASE_DIR` を `scripts/legacy_country` の親の親（プロジェクトルート）に設定しています
- 新規開発は `scripts/pipeline_merged/` を利用してください
