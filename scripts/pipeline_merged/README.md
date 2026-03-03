# pipeline_merged

合体 Excel 用パイプライン（司令塔①・②・export_for_leaflet）

## 概要

`excel_local_merged/` の合体 Excel（cn300_北中アメリカ.xlsx, cn400_500_南米オセアニア.xlsx）を入力とし、GeoNames マッチングを行うパイプラインです。

## 実行方法（案 C: モジュール実行）

プロジェクトルートで以下を実行してください。Mac / Windows 共通です。

```bash
# 司令塔①（合体Excel用）
python -m scripts.pipeline_merged.run_local_build

# 司令塔②
python -m scripts.pipeline_merged.run_stage_match

# Leaflet 用 GeoJSON 出力
python -m scripts.pipeline_merged.export_for_leaflet
```

## 前提

1. **Excel 合体**: `python -m scripts.prepare_excel.merge_excel` で正本データを作成済みであること
2. **geonames_master.pkl**: プロジェクトルートに存在すること
3. **config/overseas_territories.json**: 海外領土設定

## 入力・出力

| 段階 | 入力 | 出力 |
|------|------|------|
| 司令塔① | excel_local_merged/*.xlsx | output_match_name/, output_match_alternatenames/, output_match/ |
| 司令塔② | output_match_name/*_name.xlsx | output_match_results/ |
| export_for_leaflet | output_match_results/, output_match_name/ | output_leaflet/ |

## 比較用

国毎の旧パイプラインは `scripts/legacy_country/` にあります。
