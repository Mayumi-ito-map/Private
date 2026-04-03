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
3. **geonames_worldwide_terrain.pkl**: 全世界モードで使用（生成方法は下記）
4. **config/overseas_territories.json**: 海外領土設定（国毎モード）

## 全世界マッチングの実行手順

全世界モード（`--worldwide`）は、海・山・海底地形など国境をまたぐ地名を `geonames_worldwide_terrain.pkl` で一括マッチングします。

### 手順1: geonames_master.pkl の生成（既にあればスキップ）

```bash
cd /Users/itoumayumi/Desktop/project
python build_geonames_db.py
```

`allCountries.txt` と `alternateNames.txt` から `geonames_master.pkl` を生成します。

### 手順2: geonames_worldwide_terrain.pkl の生成

```bash
cd /Users/itoumayumi/Desktop/project
python build_geonames_worldwide_terrain.py
```

`geonames_master.pkl` から `fcl` が T（地形）/ H（水系）/ U（海底地形）/ V（植生）のレコードを抽出し、`geonames_worldwide_terrain.pkl` を生成します。

### 手順3: 全世界マッチングの実行

```bash
cd /Users/itoumayumi/Desktop/project/scripts/pipeline_merged
python run_local_build.py --worldwide
```

結果は `output_match_worldwide/` に出力されます。

### 流れのまとめ

| 手順 | コマンド | 生成物 |
|------|----------|--------|
| 1 | `python build_geonames_db.py` | `geonames_master.pkl`（既にあればスキップ） |
| 2 | `python build_geonames_worldwide_terrain.py` | `geonames_worldwide_terrain.pkl` |
| 3 | `python run_local_build.py --worldwide` | `output_match_worldwide/*_terrain_phase1_2.xlsx` |

`geonames_master.pkl` が既にある場合は手順2から始めてください。

## 入力・出力

| 段階 | 入力 | 出力 |
|------|------|------|
| 司令塔①（国毎） | excel_local_merged/*.xlsx | output_match_name/, output_match_alternatenames/, output_match/ |
| 司令塔①（--worldwide） | excel_local_merged/*.xlsx | output_match_worldwide/*_terrain_phase1_2.xlsx |
| 司令塔② | output_match_name/*_name.xlsx | output_match_results/ |

## 比較用

国毎の旧パイプラインは `scripts/legacy_country/` にあります。
