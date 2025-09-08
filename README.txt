paypay取引履歴→マネーフォワードMEへの登録方法

フォルダ階層
paypay_to_mf
|
|- convert_paypay_to_mf.py
|- mf_import_csv.py
|- paypay_csv
  |- paypay取引履歴.csv
|- mf_csv
  |- paypay取引履歴変換後.csv



1. paypayの取引履歴から対象の日付を選択してダウンロードし、PCに転送する
2. paypay_csvフォルダに、1でダウンロードしたファイルを保存。
　→「paypay取引履歴.csv」にあたる
3. python convert_paypay_to_mf.py ./paypay_csv/paypay取引履歴.csv ./mf_csv/paypay取引履歴変換後.csvでマネーフォワードMEに対応したcsv形式に変換する
　→「paypay取引履歴変換後.csv」にあたる
4.python mf_import_csv.py  ./mf_csv/paypay取引履歴変換後.csvでマネーフォワードに自動で登録される