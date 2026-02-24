# Leaflet 国一覧「index.json → data_index.js」変更の学習用参照

初めての経験として、変更前のスクリプトとレポートをセットで残すためのメモです。

## 保存しているファイル

| ファイル | 説明 |
|----------|------|
| **build_leaflet_index_変更前.py** | 変更前のスクリプト（index.json のみ出力）。学習用に別名で保存。 |
| **build_leaflet_index.py** | 現在のスクリプト（index.json ＋ data_index.js を出力）。通常はこちらを実行。 |

## あわせて読むとよいレポート（memo 内）

- **Leaflet見本と今回の違い_index.json.md**  
  - 見本（index_fr.html）は index.json を使っていない理由、fetch の相対パスの問題の説明。
- **旧地名地図と今回の設計の違い.md**  
  - 旧地名地図（52.194.188.168）と今回の地図の設計の違い（固定サーバ vs ローカル、一覧の持ち方）。
- **Leaflet地図の指示と使い方.md**  
  - 起動手順、data_index.js を使う理由（どこでも表示できるようにするため）。

## 変更の要点（学習用）

1. **変更前**: 国一覧は index.json だけ。leaflet_map.html は fetch("index.json") で読む。  
   → 開く URL やサーバの起動場所によっては「index.json が見つかりません」になる。

2. **変更後**: build_leaflet_index.py が data_index.js も出力。  
   - data_index.js の内容は `window.LEAFLET_COUNTRY_INDEX = [ ... ];` の形。
   - leaflet_map.html で `<script src="data_index.js"></script>` で読み、一覧はこの変数を使う。
   - 見本（旧地名地図）と同じ「一覧を script で読む」方式なので、fetch に依存せず、どこでもプルダウンが表示される。

3. **フォールバック**: data_index.js が無い場合は、従来どおり fetch("index.json") で国一覧を取得する。
