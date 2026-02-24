### 司令塔②＿以下は旧スクリプトを作成した際の指示書になります。
世界大地図帳（ローカル）の国毎の地名Excelファイルを司令塔①スクリプト「run_local_build.py」で処理をした結果をoutput_matchに出力しました。
output_matchの中には、国毎のExcelファイル（191項目）が入って下り、そのファイルの列名「normalized_name」を使用します。
output_match/Excel/列名「normalized_name」
Excelファイルはファイル名は「cn002_AZ_アゼルバイジャン_result.xlsx」のようになっており、アンダーバーで分割して、国コードを取得できます。上記の例では「AZ」が国コードになります。
この国毎のExcelファイルを、GeoNamesの国毎のjsonファイルと国同士（同一の2桁国コード）でマッチングします。
GeoNamesの国毎のjsonは、「output_json」フォルダに国毎にはいっています。「AD_dict.json」などの国コードのjsonファイルです。
"(( Vranovic ))": [
    {
      "alternatenames": "(( Vranovic )),(( Vranović ))",
      "asciiname": "Vranovici",
      "cc": "BA",
      "cc2": "",
      "fcl": "P",
      "fcode": "PPL",
      "geonameid": "3187344",
      "name": "Vranovići"
    }
  ],
  "(( Vranović ))": [
    {
      "alternatenames": "(( Vranovic )),(( Vranović ))",
      "asciiname": "Vranovici",
      "cc": "BA",
      "cc2": "",
      "fcl": "P",
      "fcode": "PPL",
      "geonameid": "3187344",
      "name": "Vranovići"
    }
  ],
のように、地名データが「name」「asciiname」「alternatenames」に入っています。

「alternatenames」は、カンマ区切りの文字列のため、ロードした直後にまずリスト化してください。
GeoNamesについては、
{
  name: str,
  asciiname: str,
  alternatenames: list[str]
}
となります。

Excelファイルは海外領土を持っている国が9ヶ国あり、その場合は対象となる国名が増えます。対応表は「overseas_territories.json」で、中身は｛"NL": [ "AW","BQ","CW","NL","SX"],｝となっています。つまりExcelファイルのNLは、GeoNamesのAW、BQ、CW、NL、SXとマッチングすることになります。

Excelファイルの列名「normalized_name」には、地名データがリストになって入っています。
["J. an Nabī Shu'ayb", "Jebel an Nabī Shu'ayb", "Jsbal an Nabī Shu'ayb"]
['Wādī Hadramawt']
['Ash Shaykh ʻUthman']
のように、リストの中身は1つ以上です。
Excelファイルの列名「judge」が0に該当する列名「normalized_name」だけ使用します。「judge」が「1、」「2+」の列名「normalized_name」は使用しません。

matchers/stage_matcher.pyのスクリプトは、正規表現の関数が書かれています。関数のStageは3段階で、Stageごとに正規化強度を上げています。
matchers/stage_matcher.pyをモジュールとして読み込んで使用します。

Excelファイルの列名「normalized_name」の地名データと、GeoNamesの国毎のjsonファイルの地名データ「"name"」「"asciiname"」「"alternatenames"」に対してStage1、Stage2、Stage3の順番でマッチングを行います。
Stage1でマッチングしたら、その結果を記録して、次のStage2、Stage3は行いません。
記録には、マッチングしたGeoNamesの国毎のjsonファイルの地名データGeoNamesの情報が必要です。複数マッチングするので、記録は「Stage1_hit」列を作成し、その列にマッチングしたGeoNamesの国毎のjsonファイルの地名データ（正規化する前のGeoNamesのjsonデータ）をリストで入れます。
同一GeoNames IDが有った場合は、重複を削除してユニークにしてください。


Stage2、Stage3も同様に「Stage2_hit」「Stage3_hit」列に記録します。
集計用の「world_summary.xlsx」を作成し、国毎のマッチング結果を記録します。列名は、
country	ローカルのExcelファイル名を記載します。（例：cn010_IN_インド_result）拡張子は不要です。
total_0_target	「normalized_name」の地名データの総数を記載します。
stage1	「Stage1_hit」の地名データの数を記載します。
stage1(%)	「stage1」の数/「total_0_target」の数を記載します。
stage2	
stage2(%)	
stage3	
stage3(%)	
still_0	stage1、stage2、stage3のいずれにもマッチングしなかった地名データの数を記載します。
till_0(%) still_0の数/「total_0_target」の数を記載します。