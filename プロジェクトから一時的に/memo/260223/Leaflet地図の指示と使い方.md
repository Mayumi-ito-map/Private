# Leaflet地図の指示と使い方

## 実装した内容（指示への対応）

- **地図と連動した地名一覧**: 右側一覧は Excel の行順（original_row）。左が地図。ピンと一覧は連動。
- **国毎**: プルダウンで国を選ぶとその国の GeoJSON を読み込み、地図・一覧を表示。
- **プルダウンの順番**: `index.json` の cn 数字順。**5エリアでグループ表示**（アジア / ヨーロッパ / アフリカ / 北アメリカ・中央アメリカ / 南アメリカ・オセアニア / その他）。
- **一覧の表示**: local_ID、Japanese、English。ページングは「1/29（全1357件）」形式。（）内は Local 地名の総数（＝一覧の行数）。
- **地図上側のバー**: 選択した行の English、Japanese、local_ID、local_cat、local_lat、local_lon を表示。
- **5色の凡例**: 地図上部に local / geonames_hits / Stage1_hit / Stage2_hit / Stage3_hit の色を表示。
- **背景地図**: レイヤー切替で OpenStreetMap と Google を選択可能（右上コントロール）。
- **ピン↔一覧の連動**: ピンクリックで該当行をハイライト（緑背景）・該当ページへスクロール。一覧の行クリックでその行のピンにズームしポップアップ表示。
- **ポップアップ**: Local は local_ID, Japanese, English, local_cat。GeoNames は geonameid, name, feature_class, feature_code。
- **拡大縮小**: Leaflet 標準のズーム（マウスホイール・＋－ボタン）。

## 5エリアの分け方

`build_leaflet_index.py` で cn 数字の範囲を次のように分類しています。

| cn 範囲 | エリア |
|---------|--------|
| 002〜080 | アジア |
| 101〜145 | ヨーロッパ |
| 201〜272 | アフリカ |
| 301〜323 | 北アメリカ・中央アメリカ |
| 401〜516 | 南アメリカ・オセアニア |
| 上記以外 | その他 |

プルダウンは **optgroup** でエリアごとにグループ化し、その中で cn 順に並べています。

## ファイル構成

- **output_leaflet/**
  - **index.json** … 国一覧（build_leaflet_index.py で生成）
  - **cn002_AZ_アゼルバイジャン.geojson** 等 … 国別 GeoJSON（build_geojson_leaflet.py で生成）
  - **leaflet_map.html** … 地図＋一覧の単一ページ

## 起動手順

1. **GeoJSON と国一覧の準備**
   - `python build_geojson_leaflet.py` で output_leaflet に *.geojson を出力。
   - `python build_leaflet_index.py` で **index.json** と **data_index.js** を生成。

2. **同じフォルダにまとめる（複数人・どこでも表示するため）**
   - **leaflet_map.html** と **data_index.js** と ***.geojson** を同じフォルダ（`output_leaflet/`）に置く。
   - 国一覧は **data_index.js** を &lt;script src="..."&gt; で読むため、fetch のパスに依存しない（見本の旧地名地図と同じ方式）。

3. **必ず http:// で開く（旧地名地図と同じ仕様）**
   - 旧地名地図は **http://52.194.188.168/** のように **http://** で配信されています。
   - ローカルでも **file:// では動きません。** ブラウザが file:// からの fetch をブロックするため、「GeoJSONの読み込みに失敗しました … Failed to fetch」になります。
   - **必ずローカルサーバで http:// から開いてください。**
   - **方法A（推奨）**: `output_leaflet` でサーバを起動し、http で開く。
     ```bash
     cd output_leaflet
     python -m http.server 8000
     ```
     ブラウザの URL バーに **`http://localhost:8000/leaflet_map.html`** と入力して開く。
   - **方法B**: プロジェクトルートでサーバを起動している場合は、**`http://localhost:8000/output_leaflet/leaflet_map.html`** で開く。
   - file:// で開いたときは、画面上部に「http:// で開いてください」の案内が表示されます。

4. プルダウンで「cn002_AZ_アゼルバイジャン」等を選ぶと、その国の地図と一覧が表示されます。

## Google 地図について

地図レイヤーに「Google」を入れていますが、タイル利用には Google の利用規約・API キーが必要な場合があります。本番で使う場合は要確認です。OpenStreetMap のみでも動作します。
