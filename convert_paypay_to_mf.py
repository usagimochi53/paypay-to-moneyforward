# convert_paypay_to_mf_display.py
# -*- coding: utf-8 -*-
import sys
import csv
import os
from datetime import datetime

HEAD_IN = ["取引日","出金金額（円）","入金金額（円）","海外出金金額","通貨","変換レート（円）",
           "利用国","取引内容","取引先","取引方法","支払い区分","利用者","取引番号"]

HEAD_OUT = ["日付","内容","金額（円）","保有金融機関","大項目","中項目","メモ","振替","ID"]

# 簡易カテゴリーマッピング（必要に応じて増やしてください）
# キーは「取引先」に含まれるキーワード（部分一致・大小文字の区別なし）
CATEGORY_MAP = [
    # 食費 - 食料品
    (["ミスタードーナツ", "イズミヤ", "成城石井", "スーパー", "S-PAL", "エーワンベーカリー"], ("食費", "食料品")),
    # 食費 - 外食
    (["坂井珈琲", "リンガーハット", "ケンタッキー", "一風堂", "JR-PLUS", "ベーカリー", "カフェ"], ("食費", "外食")),
    # エンタメ
    (["TOHOシネマズ", "MOVIX", "映画"], ("教養・教育", "映画・音楽・ゲーム")),
    # 交通（例：JR関連）
    (["JR", "新大阪", "仙台駅構内"], ("交通", "電車")),
    # コンビニ
    (["セブン-イレブン", "ローソン", "ファミリーマート"], ("食費", "食料品")),
]

def parse_amount(s: str):
    if s is None:
        return None
    s = s.strip().replace(",", "")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def format_amount_minus1dec(x):
    """絶対値を取り、マイナスで小数1桁にフォーマット（例: -399.0）"""
    if x is None:
        return ""
    return f"{-abs(float(x)):.1f}"

def parse_date(d: str) -> str:
    d = (d or "").strip()
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y/%m/%d")
        except ValueError:
            pass
    if " " in d:
        return parse_date(d.split(" ")[0])
    return d  # 最後の手段

def guess_category(merchant: str):
    name = (merchant or "").lower()
    for keywords, (large, middle) in CATEGORY_MAP:
        for kw in keywords:
            if kw.lower() in name:
                return large, middle
    return "", ""

def main():
    if len(sys.argv) < 2:
        print("usage: python convert_paypay_to_mf_display.py input_paypay.csv [output_mf.csv]")
        sys.exit(1)

    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) >= 3 else os.path.splitext(in_path)[0] + "_mf.csv"

    with open(in_path, "r", encoding="utf-8-sig", newline="") as fin, \
         open(out_path, "w", encoding="utf-8-sig", newline="") as fout:

        reader = csv.reader(fin)
        writer = csv.writer(fout)

        first = next(reader, None)
        if not first:
            print("入力が空です。")
            sys.exit(1)

        # ヘッダ行判定（なければ先頭行から処理する）
        if first[0] != "取引日":
            fin.seek(0)
            reader = csv.reader(fin)

        writer.writerow(HEAD_OUT)

        for row in reader:
            if not row:
                continue

            # 列安全取り出し
            def col(i): return row[i] if i < len(row) else ""

            pp_date     = col(0)
            pp_out      = col(1)  # 出金
            # pp_in     = col(2)  # 入金（今回は使わない＝支払いのみ）
            pp_kind     = col(7)  # 取引内容
            pp_merchant = col(8)  # 取引先
            pp_method   = col(9)  # 取引方法
            pp_ref      = col(12) # 取引番号

            # 「支払い」以外は除外
            if pp_kind.strip() != "支払い":
                continue

            out_amt = parse_amount(pp_out)
            if out_amt is None:
                # 金額が無い支払いはスキップ
                continue

            mf_date = parse_date(pp_date)
            content = f"支払い {pp_merchant}".strip()
            amount  = format_amount_minus1dec(out_amt)
            large, middle = guess_category(pp_merchant)
            memo    = f"方法:{pp_method.strip()} / 取引番号:{pp_ref.strip()}".strip()

            writer.writerow([
                mf_date,         # 日付
                content,         # 内容（支払い + 取引先）
                amount,          # 金額（円） - 小数1桁 - マイナス
                "PayPay",        # 保有金融機関
                large,           # 大項目（マッピングにあれば）
                middle,          # 中項目（マッピングにあれば）
                memo,            # メモ
                0,               # 振替
                ""               # ID（ご指定に合わせて空欄にします）
            ])

    print(f"✅ 変換完了: {out_path}")

if __name__ == "__main__":
    main()
