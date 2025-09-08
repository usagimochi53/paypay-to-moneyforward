# coding: UTF-8
import sys
import time
import csv
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ===== ヘルパー =====
def to_int_yen(s: str) -> int:
    """ ' -1,077.0 ' → -1077 / 空は0 """
    s = (s or "").replace(",", "").strip()
    if s == "":
        return 0
    return int(round(float(s)))


def wait_one_of(driver, locators, timeout=15, clickable=False):
    """複数候補のうち最初に見つかった要素を返す"""
    last_exc = None
    for by, value in locators:
        try:
            if clickable:
                return WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((by, value))
                )
            else:
                return WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
        except TimeoutException as e:
            last_exc = e
            continue
    raise NoSuchElementException(f"Element not found for any of: {locators}") from last_exc


def ensure_input_page(driver, input_url):
    """profile/rule#custom-end-day に飛ばされたら強制で INPUT_URL に戻す。"""
    for _ in range(3):
        cur = driver.current_url
        if "moneyforward.com/profile/rule" in cur:
            print("⚠️ custom-end-day に遷移 → INPUT_URL に戻します")
            driver.get(input_url)
            try:
                WebDriverWait(driver, 10).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "cf-new-btn")),
                        EC.url_contains("/cf")
                    )
                )
            except TimeoutException:
                continue
        else:
            break
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CLASS_NAME, "cf-new-btn"))
    )


def click_cf_new(driver, index=1, timeout=15):
    """cf-new-btn の index 番目をクリックして手入力モーダルを開く（index=1: 2個目）"""
    WebDriverWait(driver, timeout).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "cf-new-btn"))
    )
    btns = driver.find_elements(By.CLASS_NAME, "cf-new-btn")
    if len(btns) <= index:
        raise NoSuchElementException(f"cf-new-btnが {index+1} 個以上ありません（len={len(btns)}）")
    target = btns[index]
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
    try:
        target.click()
    except Exception:
        driver.execute_script("arguments[0].click();", target)


def open_entry_form(driver, input_url, use_continue_first=True):
    """入力モーダルを開く。
    1) まずはモーダルの"続けて入力する"ボタンがあればクリック（連続入力用）
    2) なければ cf-new-btn(index=1) をクリック
    """
    # 1) 既存モーダルの続きボタンを優先
    if use_continue_first:
        try:
            cont = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.ID, "confirmation-button"))
            )
            # 表示状態か確認
            style = cont.get_attribute("style") or ""
            if "display: none" not in style:
                cont.click()
                # 新しい空フォームの主要項目が出るまで待機
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "updated-at")))
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "appendedPrependedInput")))
                return
        except Exception:
            pass

    # 2) ボタンが無い/押せない場合はページのボタンから開く
    ensure_input_page(driver, input_url)
    click_cf_new(driver, index=1)
    # モーダル出現待ち
    wait_one_of(
        driver,
        [
            (By.ID, "form-user-asset-act"),
            (By.CSS_SELECTOR, "form#form-user-asset-act"),
            (By.ID, "updated-at"),
        ],
        timeout=15
    )


# ===== URL / アカウント =====
LOGIN_URL = "https://id.moneyforward.com/sign_in"
INPUT_URL = "https://moneyforward.com/cf#cf_new"

user = "メールアドレス"
password = "パスワード"

# ===== メイン =====
if len(sys.argv) != 2:
    print("No input_file!")
    print("usage: python mf_import_csv.py sample.csv")
    sys.exit(1)
input_file = str(sys.argv[1])

try:
    print("Start :" + input_file)

    # Chrome（シークレット）起動
    options = webdriver.ChromeOptions()
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument("--incognito")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)

    # ログイン
    driver.get(LOGIN_URL)

    email = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
    email.clear()
    email.send_keys(user, Keys.ENTER)

    pw = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    pw.clear()
    pw.send_keys(password, Keys.ENTER)

    # OTP（出た時のみ）
    try:
        otp_elem = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name*='otp']"))
        )
        otp_code = input("二段階認証コードを入力してください: ")
        otp_elem.clear()
        otp_elem.send_keys(otp_code, Keys.ENTER)
        print("✅ OTP送信完了")
    except TimeoutException:
        print("OTP入力は表示されませんでした。")

    # ログイン完了を待つ
    WebDriverWait(driver, 60).until(EC.url_contains("moneyforward.com"))

    # 手入力画面へ → もし custom-end-day に飛ばされたら戻す
    driver.get(INPUT_URL)
    ensure_input_page(driver, INPUT_URL)

    # ===== CSV 読み込み（BOM対策） =====
    with open(input_file, mode="r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        n = 0
        for row in reader:
            n += 1
            # ヘッダ / 振替 / コメント行スキップ
            if n == 1 and row and row[0] == "日付":
                print(f"[{n}] Skip header line")
                continue
            if len(row) > 7 and str(row[7]).strip() in ("1", "true", "TRUE"):
                print(f"[{n}] Skip 振替: {row}")
                continue
            if row[0] in ("#", "0", "計算対象"):
                print(f"[{n}] Skip line")
                continue

            print(f"[{n}] Import row: {row}")

            # 入力モーダルを開く（まずは続けて入力→なければ cf-new-btn index=1）
            open_entry_form(driver, INPUT_URL, use_continue_first=True)

            # ===== モーダル要素 =====
            modal = wait_one_of(
                driver,
                [
                    (By.ID, "form-user-asset-act"),
                    (By.CSS_SELECTOR, "form#form-user-asset-act"),
                ],
                timeout=15
            )

            # 主要フィールド待ち
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "updated-at")))
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "appendedPrependedInput")))

            # ===== 日付 =====
            date_input = modal.find_element(By.ID, "updated-at")
            date_input.clear()
            time.sleep(0.2)
            date_input.send_keys(row[0])
            date_input.click(); date_input.click()
            time.sleep(0.2)

            # ===== 金額と支出/収入の切り替え =====
            amt_raw = to_int_yen(row[2])
            amount = abs(amt_raw)

            if amt_raw > 0:
                # 収入
                try:
                    modal.find_element(By.CLASS_NAME, "plus-payment").click()
                except NoSuchElementException:
                    pass
            else:
                # 支出（明示）
                try:
                    modal.find_element(By.CLASS_NAME, "minus-payment").click()
                except NoSuchElementException:
                    pass

            amt_box = modal.find_element(By.ID, "appendedPrependedInput")
            amt_box.clear()
            amt_box.send_keys(str(amount))

            # ===== sub_account_id_hash を "なし" (value=0) に選択 =====
            try:
                sub_select = modal.find_element(By.ID, "user_asset_act_sub_account_id_hash")
                driver.execute_script("arguments[0].value='0'; arguments[0].dispatchEvent(new Event('change'));", sub_select)
            except NoSuchElementException:
                pass

            # ===== 大項目 =====
            if len(row) > 4 and row[4] and row[4] != "未分類":
                modal.find_element(By.ID, "js-large-category-selected").click()
                wait_one_of(driver, [(By.LINK_TEXT, row[4])], timeout=10, clickable=True).click()

            # ===== 中項目 =====
            if len(row) > 5 and row[5] and row[5] != "未分類":
                sub_category = row[5].lstrip("'")
                modal.find_element(By.ID, "js-middle-category-selected").click()
                wait_one_of(driver, [(By.LINK_TEXT, sub_category)], timeout=10, clickable=True).click()

            # ===== 内容（メモがあれば括弧） =====
            memo = row[6] if len(row) > 6 else ""
            content = row[1] if not memo else f"{row[1]}（{memo}）"
            content = content[:50]
            content_el = modal.find_element(By.ID, "js-content-field")
            content_el.clear()
            content_el.send_keys(content)

            # ===== 保存 → 続けて入力 =====
            time.sleep(0.4)
            modal.find_element(By.ID, "submit-button").click()

            # 保存後、"続けて入力する" が表示されたら次のループで活用（ここでは軽く待つだけ）
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "confirmation-button"))
                )
            except TimeoutException:
                pass

            # 軽いインターバル
            time.sleep(0.8)

finally:
    print("End :" + input_file)
    try:
        driver.quit()
    except Exception:
        pass
