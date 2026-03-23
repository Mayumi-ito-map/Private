# pipeline_merged

合体 Excel 用パイプライン（司令塔①・②）

## 概要

`excel_local_merged/` の合体 Excel（cn300_北中アメリカ.xlsx, cn400_500_南米オセアニア.xlsx）を入力とし、GeoNames マッチングを行うパイプラインです。

## 実行方法（案 C: モジュール実行）

プロジェクトルートで以下を実行してください。Mac / Windows 共通です。

```bash
# 司令塔①（合体Excel用・国毎マッチング）
python -m scripts.pipeline_merged.run_local_build

# 司令塔①（全世界モード・海山地名）
python -m scripts.pipeline_merged.run_local_build --worldwide

# 司令塔②
python -m scripts.pipeline_merged.run_stage_match
```

## 前提

1. **Excel 合体**: `python -m scripts.prepare_excel.merge_excel` で正本データを作成済みであること
2. **geonames_master.pkl**: プロジェクトルートに存在すること（国毎モード）
3. **geonames_worldwide_terrain.pkl**: `build_geonames_worldwide_terrain.py` で生成（全世界モード）
4. **config/overseas_territories.json**: 海外領土設定（国毎モード）

## 入力・出力

| 段階 | 入力 | 出力 |
|------|------|------|
| 司令塔①（国毎） | excel_local_merged/*.xlsx | output_match_name/, output_match_alternatenames/, output_match/ |
| 司令塔①（--worldwide） | excel_local_merged/*.xlsx | output_match_worldwide/*_terrain_phase1_2.xlsx |
| 司令塔② | output_match_name/*_name.xlsx | output_match_results/ |

## 比較用

国毎の旧パイプラインは `scripts/legacy_country/` にあります。
