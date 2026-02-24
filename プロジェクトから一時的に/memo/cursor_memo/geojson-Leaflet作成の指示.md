### geojson,Leaflet作成の指示_26-02-23

生成されたExcelファイルから、国毎にGeoJSON形式のファイルを作成します。
必要な項目を書きました。

**実行スクリプト**: `build_geojson_leaflet.py`  
入力: `output_match_results_quote_variants` の Excel／出力: `output_leaflet/*.geojson`

- properties の **type**: `"Local"`（ローカル地点）／`"GeoNames"`（GeoNames 候補）。色分け用の **hit_type** は別途あり。
- **中国・韓国で Local が「空白」になる理由**: 元 Excel の `local_lat` / `local_lon` が空欄や非数値（NaN）の行は、無効な座標になるため GeoJSON では **Local の Point を出力しない**ようにしている。そのため地図上に Local が表示されない。GeoNames 側はヒットがあれば従来どおり出力される。

localのExcelファイルの列名から、幾つか必要な項目があります。
テーブルにしています。

色分けは、5つを色分けで表示します。
local,
geonames_hits,
Stage1_hit,
Stage2_hit,
Stage3_hit

geonamesデータの必要な項目も以下に示しています。


#### localデータ
入力
output_match_results_quote_variants

出力
output_leaflet
cn002_AZ_アゼルバイジャン.geojson  「_result」不要

excel_local/Excelファイル
必要な列名と、表示の変換一覧です。
|列名|表示|
| ---- | ---- |
|index_ID|local_ID|
|修正後和文地名|Japanese|
|修正後欧文地名|English|
|num |local_cat|
|local_lat|local_lat|
|local_lon|local_lon|

marker-color: #ff0000


#### GeoNamesデータ

入力
geonames_master.pkl

必要な項目
"geonameid"
"name"
"asciiname"
"alternatenames"
"latitude"
"longitude"
"feature_class"
"feature_code"
"country_code"

marker-color:
geonames_hits : #0000ff
Stage1_hit : #ffc800
Stage2_hit : #00ff00
Stage3_hit : #de47d9

---

ここまでのスクリプトで、geopandasは使用しないのでしょうか？ 
またgeopandasのメリットは何でしょうか？  
どういう場合に使用しますか？  
地名データベースで使用するならば、一般的にどんな場合でしょうか？

---

**回答の要約**
1. ここまでのスクリプトで geopandas は使っているか
GeoJSON を作るスクリプト（build_geojson_leaflet.py や export_for_leaflet.py）では使っていません。
どちらも「辞書・リストで GeoJSON を組み立てて json.dump で書き出す」だけです。
geopandas が出てくるのは geonames_loader.py だけです。
records_to_gdf() で地名レコードを GeoDataFrame に変換している
get_geonames_for_country() の返り値の一つとして gdf を返している
ただし 司令塔①②（run_stage_match_, run_local_build）では gdf は受け取っているだけで未使用で、実際に使っているのは placename_dict と records だけです。

2. geopandas のメリット
地理データを「表」で扱える
pandas の DataFrame に geometry（Point など）が乗った形で、属性と位置を一緒に扱える。
空間演算が使える
距離・「このポリゴンに含まれるか」・「近い順に N 件」などをメソッドで書ける。
座標系（CRS）を管理できる
緯度経度とメートル系の変換や、to_crs() での統一がしやすい。
GeoJSON / Shapefile などの入出力
read_file() / to_file() で読み書きできる。

3. どういう場合に使うか
ある点が「どの範囲（国・県・メッシュなど）に含まれるか」を判定したい
「ある地点から近い順に N 件」のような近傍検索をしたい
距離・面積を、球面や投影座標でちゃんと計算したい
複数の地理レイヤー（点・ポリゴン）を重ねて結合・クリップしたい
といった「位置や範囲に基づく処理」をするときに使うと便利です。

4. 地名データベースでよくある使い方
* 空間結合
  * 地名の緯度経度を、国・州・県のポリゴンと突き合わせて「どの行政区に属するか」を付与する。
* 近傍・距離順
  * ある地名に「最も近い GeoNames 候補」を距離でランキングする。
* 重複・近接の検出
  * ほぼ同じ位置の候補をマージしたり、一定距離以内の点をグルーピングする。
* 地図用の書き出し
  * GeoDataFrame をそのまま GeoJSON や Shapefile に書き出して、Leaflet や QGIS に渡す。

このプロジェクトでは、今は「名前の文字列マッチング」が中心で、距離・範囲・ポリゴンを使う処理がほとんどないため、現状の GeoJSON 生成だけなら geopandas は必須ではありません。
一方で、
「ローカル地点と GeoNames の距離を共通ロジックで計算したい」  
「候補を距離順で並べたい」  
「行政区ポリゴンと結合したい」  
といった処理を増やすなら、geopandas（と geonames_loader の gdf）を活用する価値があります。
上記の整理は memo/geopandasの利用とメリット.md に書いてあります。

---
### Leaflet地図の指示

見本1の様な、地図と連動した地名の一覧を作成したいです。
目的はマッチングした1つあるは複数の地名について距離を測り、1つのGeoNamesIDを取得するためになります。

国毎に地図を作成します。

地図の順番は、Excelのファイル名の「cn数字」の順で、プルダウンで「cn002_AZ_アゼルバイジャン」と表示します。
* 002AZ~080PS･･･アジア
* 101IS〜145RU･･･ヨーロッパ
* 201DZ〜272EH･･･アフリカ
* 301US〜323MX･･･北アメリカ、中央アメリカ
* 401AR〜516FM･･･南あめりか、オセアニア
全体で193項目ありますので、上記の5つのエリアに分類する方法があっても分かりやすいです。
あるいは、5つのエリアに分けるならば、どんな方法が考えられるでしょうか？

右側の一覧は、Excelの行の順番にしてください。
ExcelのID「local_ID」
Excelの日本語地名「Japanese」
Excelの欧文地名「Einglish」
数が入り切らない場合は、「1/29（全1357件）」のようにして（）内にはloclの地名の合計を入れてください。
地図の上側には、
「Einglish」「Japanese」「local_ID」「local_cat」「local_lat」「local_lon」

地図内の「ピン」は 5色で色分け。
可能ならば、地図の上部に凡例を入れてください。
local : #ff0000
geonames_hits : #0000ff
Stage1_hit : #ffc800
Stage2_hit : #00ff00
Stage3_hit : #de47d9

背後の地図は、
OpenStreetMap
GoogleMap
を切り替えてて表示します。

右側の一覧とピンは連動しております。
ピンをクリックすると一覧の地名の四角の色が変わります。「日本の見本_4.png」
また、クリックするとポップアップで、表示します。
Localは、
「local_ID」
「Japanese」
「Einglish」
「local_cat」
GeoNamesは、
「geonameid」
「name」
「feature_class」
「feature_code」

地図は拡大縮小できるようにしてください。

----
### 回答：変更内容
1. index.json の読み込みパスを明示
leaflet_map.html で、この HTML があるフォルダを基準にパスを決めるようにしました。
BASE = new URL(".", window.location.href).href で「今開いている HTML のフォルダ」を取得
index.json → BASE + "index.json"
国別 GeoJSON → BASE + file
このため、
http://localhost:8000/output_leaflet/leaflet_map.html で開いている
→ index.json は http://localhost:8000/output_leaflet/index.json として読みに行く
http://localhost:8000/leaflet_map.html で開いている（output_leaflet でサーバ起動）
→ index.json は http://localhost:8000/index.json として読みに行く
どちらの開き方でも、HTML と index.json が同じフォルダにあれば index.json が参照されます。
2. 「index.json が見つかりません」が出る場合の確認
次の2点を確認してください。
build_leaflet_index.py を実行したあと、output_leaflet/index.json ができているか
プロジェクトルートで:
python build_leaflet_index.py
生成されるファイル: output_leaflet/index.json
ブラウザで開いている URL
推奨: ターミナルで cd output_leaflet → python -m http.server 8000 とし、
http://localhost:8000/leaflet_map.html を開く。
プロジェクトルートで python -m http.server 8000 している場合は、
http://localhost:8000/output_leaflet/leaflet_map.html を開く（パスに output_leaflet/ を含める）。
file:// で開いていると index.json の読み込みがブロックされるため、必ず上記のように http:// で開いてください。

---
### フランスの見本との違いは何か？
project/LeafletMap見本/index_fr.html　で作った際には、このような事は発生していません。違いは何故なのでしょうか？

---
### 旧地名のソースとの違いは何か？

「旧地名地図と今回の設計の違い.pdf」を見て、  
フランスの見本はindex.jsonを使っていない、fetchの相対パスの件もおおよそ理解できました。
見本日本の見本_2.png」はスクリーンショットをとったものですが、実際に動いている見本をもらいました

旧地名地図
http://52.194.188.168/

この数字を検索バーにいれると起動します。
わたしのPCで起動し、作業者のPCとは違います。
この設計との違いは何でしょうか？

52.194.188.168
 のソースを送ります。複数人で分業して作業を行うので、
なんとか解消して、どこでも表示できるようにする必要があります。

---
### 旧地名のソース

```
<!DOCTYPE html>

<html lang="ja">

<head>

    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>地図データ表示</title>

    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />

    <style>

		.container {

            display: flex; /* フレックスボックスを使用 */

        }

        #map {

            flex: 3; /* 3の割合 */

            height: 900px; /* マップの高さ */

			cursor: crosshair; /* カーソルを十字に設定 */

        }

        #info {

            flex: 1; /* 1の割合 */

            margin-left: 20px; /* マップと情報の間にスペースを追加 */

        }

        .list-container {

            display: grid;

            grid-template-columns: repeat(3, 1fr); /* 3列に設定 */

            gap: 10px; /* 列間のスペース */

        }



        .item {

            font-size: 12px; /* 文字サイズを小さく設定 */

            border: 1px solid #ccc; /* アイテムの境界線 */

            padding: 2px; /* アイテムの内側の余白 */

            text-align: center; /* 中央揃え */

            cursor: pointer; /* ポインタを表示 */

            transition: background-color 0.3s; /* ホバー時の効果 */

        }

        .item:hover {

            color: darkblue; /* ホバー時の色 */

        }

    </style>

</head>

<body>

    <select id="group-selector">

		<option value="01_hokkaido">01_北海道</option>

		<option value="02_aomori">02_青森県</option>

		<option value="03_iwate">03_岩手県</option>

		<option value="04_miyagi">04_宮城県</option>

		<option value="05_akita">05_秋田県</option>

		<option value="06_yamagata">06_山形県</option>

		<option value="07_fukushima">07_福島県</option>

		<option value="08_ibaraki">08_茨城県</option>

		<option value="09_tochigi">09_栃木県</option>

		<option value="10_gunma">10_群馬県</option>

		<option value="11_saitama">11_埼玉県</option>

		<option value="12_chiba">12_千葉県</option>

		<option value="13_tokyo">13_東京都</option> 

		<option value="14_kangawa">14_神奈川県</option>

		<option value="15_niigata">15_新潟県</option>

		<option value="16_toyama">16_富山県</option>

		<option value="17_ishikawa">17_石川県</option>

		<option value="18_fukui">18_福井県</option>

		<option value="19_yamanashi">19_山梨県</option>

		<option value="20_nagano">20_長野県</option>

		<option value="21_gifu">21_岐阜県</option>

		<option value="22_sizuoka">22_静岡県</option>

		<option value="23_aichi">23_愛知県</option>

		<option value="24_mie">24_三重県</option>

		<option value="25_shiga">25_滋賀県</option>

		<option value="26_kyoto">26_京都府</option>

		<option value="27_kyotoshi">27_京都市</option>

		<option value="28_osaka">28_大阪府</option>

		<option value="29_hyougo">29_兵庫県</option>

		<option value="30_nara">30_奈良県</option>

		<option value="31_wakayama">31_和歌山県</option>

		<option value="32_tottori">32_鳥取県</option>

		<option value="33_shimane">33_島根県</option>

		<option value="34_okayama">34_岡山県</option>

		<option value="35_hiroshima">35_広島県</option>

		<option value="36_yamaguchi">36_山口県</option>

		<option value="37_tokushima">37_徳島県</option>

		<option value="38_kagawa">38_香川県</option>

		<option value="39_ehime">39_愛媛県</option>

		<option value="40_kouchi">40_高知県</option>

		<option value="41_fukuoka">41_福岡県</option>

		<option value="42_saga">42_佐賀県</option>

		<option value="43_nagasaki">43_長崎県</option>

		<option value="44_kumamoto">44_熊本県</option>

		<option value="45_ooita">45_大分県</option>

		<option value="46_miyazaki">46_宮崎県</option>

		<option value="47_kagoshima">47_鹿児島県</option>

		<option value="48_okinawa">48_沖縄県</option>

    </select>



	<!-- HTMLに2つのセレクトボックスを追加 -->

	<select id="layerSelector1">

		<option value="paleLayer">地理院淡色地図</option>

		<option value="gsiLayer">地理院標準地図</option>

		<option value="photoLayer">航空写真</option>

		<option value="oldphotoLayer">古い航空写真(zoom10-17)</option>

		<option value="tohokuLayer">東北地方太平洋岸（今昔マップ）</option>

		<option value="kantoLayer">関東（今昔マップ）</option>

		<option value="chukyoLayer">中京圏（今昔マップ）</option>

		<option value="keihanshinLayer">京阪神圏（今昔マップ）</option>

		<option value="okinawaLayer">沖縄本島南部（今昔マップ）</option>

		<option value="sapporoLayer">札幌（今昔マップ）</option>

		<option value="asahikawaLayer">旭川（今昔マップ）</option>

		<option value="hukuokaLayer">福岡・北九州（今昔マップ）</option>

		<option value="okayamaLayer">岡山・福山（今昔マップ）</option>

		<option value="osmLayer">OpenStreetMap</option>

		<option value="googleLayer">Googleマップ</option>

	</select>



	<select id="layerSelector2">

		<option value="paleLayer">地理院淡色地図</option>

		<option value="gsiLayer">地理院標準地図</option>

		<option value="photoLayer">航空写真</option>

		<option value="oldphotoLayer">古い航空写真(zoom10-17)</option>

		<option value="tohokuLayer">東北地方太平洋岸（今昔マップ）</option>

		<option value="kantoLayer">関東（今昔マップ）</option>

		<option value="chukyoLayer">中京圏（今昔マップ）</option>

		<option value="keihanshinLayer">京阪神圏（今昔マップ）</option>

		<option value="okinawaLayer">沖縄本島南部（今昔マップ）</option>

		<option value="sapporoLayer">札幌（今昔マップ）</option>

		<option value="asahikawaLayer">旭川（今昔マップ）</option>

		<option value="hukuokaLayer">福岡・北九州（今昔マップ）</option>

		<option value="okayamaLayer">岡山・福山（今昔マップ）</option>

		<option value="osmLayer">OpenStreetMap</option>

		<option value="googleLayer">Googleマップ</option>

	</select>



	<input id="opacitySlider" type="range" min="0" max="1" step="0.01" value="1">

	

	<div id="group-name" style="font-size: 24px; font-weight: bold;"></div> <!-- グループ名を表示するための要素 -->



    <div class="container"> <!-- 新しいコンテナを追加 -->

        <div id="map"></div>

        <div id="info"></div> <!-- IDとグループ名のリストを表示するための要素 -->

    </div>



    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script> 

    <script src="main.js"></script>



</body>

</html>
```
---
### 回答

見本（旧地名地図）と同じ「一覧を script で読む」方式に揃えました。これでどこで開いてもプルダウンが表示されます。

やったこと
1. 見本との違いの整理
旧地名地図（http://52.194.188.168/）のソースでは:
地域一覧が HTML の <select> に option で直書き（48都道府県）
index.json は使っていない → fetch しない
データは <script src="main.js"> で読み、パスは「HTML がある場所」基準
今回の地図は国が 193 あるので一覧を HTML に書けず、index.json を fetch で読んでいたため、「開く URL」でパスがずれていました。

2. 見本と同じ方式に変更
build_leaflet_index.py
従来どおり index.json を出力
追加で data_index.js を出力
中身: window.LEAFLET_COUNTRY_INDEX = [ { "file": "cn002_....geojson", "label": "cn002_AZ_アゼルバイジャン", "cn", "region" }, ... ];
leaflet_map.html
<script src="data_index.js"></script> を追加（見本の main.js と同じく「HTML と同じフォルダの script」で一覧を読む）
国一覧は まず window.LEAFLET_COUNTRY_INDEX を参照
無いときだけ従来どおり fetch("index.json") にフォールバック
これで「国一覧の取得」に fetch を使わないため、
プロジェクトの置き場所・誰の PC・どの URL で開いても、
leaflet_map.html と data_index.js が同じフォルダにあればプルダウンは表示されます。

3. 運用（複数人で分業するとき）
一度だけ: python build_leaflet_index.py を実行して data_index.js を生成する。
* 配るフォルダ:
leaflet_map.html と data_index.js と *.geojson を同じフォルダにまとめて渡す（ZIP や Git でよい）。
* 開き方:
ローカルなら、そのフォルダで python -m http.server 8000 して http://localhost:8000/leaflet_map.html を開く。
本番なら、そのフォルダを 52.194.188.168 のようにドキュメントルートに置く。
ポイント: 国一覧は script の読み込みで取るので、fetch の相対パスに依存しません。見本と同じ考え方です。
build_leaflet_index.py は実行済みで、output_leaflet/data_index.js も生成されています。
output_leaflet 一式をコピーして作業者に渡せば、同じように表示できます。

---
変更前の「build_leaflet_index.py」を別名で保存してください。
初めての経験なので、こちらを保存して、作っていただいたレポートとあわせて、学習したいです。

---
### 回答

保存したもの
1. 変更前スクリプト（別名）
build_leaflet_index_変更前.py
変更前の build_leaflet_index.py の内容を、この名前で保存しました。
index.json だけを出力する版です（data_index.js は出力しません）。
先頭の docstring に「変更前を別名保存したもの」「通常は build_leaflet_index.py を使うこと」を書いてあります。
2. 学習用の参照メモ
memo/Leaflet_index変更の学習用参照.md
変更前・変更後のスクリプトの役割
一緒に読むとよい memo 内レポートの一覧
「index.json のみ → index.json + data_index.js」にした変更の要点
学習時に見るとよい組み合わせ

| 用途	 | ファイル |
| --- | --- |
| 変更前のコード | 	build_leaflet_index_変更前.py |
| 変更後のコード | 	build_leaflet_index.py |
| なぜ変えたか・見本との違い	 | memo/Leaflet見本と今回の違い_index.json.md |
| 旧地名地図との設計の違い	 | memo/旧地名地図と今回の設計の違い.md |
| 変更内容の整理・参照一覧 | 	memo/Leaflet_index変更の学習用参照.md |

通常の実行では build_leaflet_index.py を使い、学習・比較用に build_leaflet_index_変更前.py と上記メモを参照できる状態にしてあります。

---
GeoJSONの読み込みに失敗しました。CV039_BN_ブルネイ･ダルエスサラーム.geojson
Failed to fetch

---
原因
URL が file:///... のため、GeoJSON の読み込み（fetch）がブロックされています。
旧地名地図: http://52.194.188.168/ → http:// で配信されているので fetch が使える
今回: file:///Users/.../leaflet_map.html → file:// のままでは、ブラウザのセキュリティで「別のローカルファイルを fetch する」ことができず Failed to fetch になる
そのため、「旧地名地図と同じ仕様」にするには、こちらも http:// で開く必要があります。
※ エラーメッセージの「CV039」は、データ上は「cn039」です。表示や写し間違いの可能性があります。
---
対処（同じ仕様にする手順）
file:// ではなく、http:// で開くようにしてください。
ターミナルで、output_leaflet フォルダに移動する
   cd /Users/itoumayumi/Desktop/project/output_leaflet
簡易サーバを起動する
   python -m http.server 8000
ブラウザの URL バーに 次を入力して開く（ファイルをダブルクリックしない）
http://localhost:8000/leaflet_map.html
これで URL が http://localhost:8000/leaflet_map.html になり、旧地名地図と同様に http 経由で GeoJSON が読み込まれます。
---
今回の変更
file:// で開いたときの案内
file:// で開いた場合、画面上部に赤系の案内を表示するようにしました。
「このページは file:// では GeoJSON を読み込めません。http:// で開いてください」「cd output_leaflet → python -m http.server 8000 → http://localhost:8000/leaflet_map.html」と表示されます。
メモの更新
memo/Leaflet地図の指示と使い方.md に、「必ず http:// で開く（旧地名地図と同じ）」「file:// では Failed to fetch になる」旨を追記しました。
---
まとめ: 旧地名地図は http で配信されているので fetch が使えます。こちらも 「ファイルを開く」ではなく、必ず python -m http.server でサーバを起動し、URL バーに http://localhost:8000/leaflet_map.html を入力して開いてください。 そうすれば同じ仕様で動きます。

---
### 地図表示の具合でtarget_hitの列がダメだった。

project/output_match_results_quote_variants/cn020_SA_サウジアラビア_result_result.xlsx
ファイルを見て下さい。
司令塔②では、target1,target2,target3と、段階的にマッチングをしています。
run_stage_match_quote_variants.py、run_stage_match_baseline.pyでは、target1でマッチングした際には、そこでマッチングは終了。target2へは進まない設計でした。列名「muched_stage」でstage1となってStage1_hitにデータが入っていますが、同様にStage2_hit,target3_hitへもデータが入っているために、地図で表示するとStage1_hitの上にStage3_hit（紫色）が重なって、stage1であることが判別できません。
よって、Stage1_hitに値が入ったら、Stage2_hit,target3_hitは空欄が望ましいです。
念のため確認ですが、段階的にマッチングになっているようですが、その部分は問題ないですね？
改めて、スクリプトを見直してください。run_stage_match_quote_variants.py、run_stage_match_baseline.pyの2つを書き換えてください。

---
