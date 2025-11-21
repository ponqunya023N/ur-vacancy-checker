import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

# --- 監視対象リスト ---
MONITORING_TARGETS = [
    {
        "danchi_name": "【S】光が丘パークタウン プロムナード十番街",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4350.html"
    },
    {
        "danchi_name": "【A】光が丘パークタウン 公園南",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3500.html"
    },
    {
        "danchi_name": "【A】光が丘パークタウン 四季の香弐番街",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4100.html"
    },
    {
        "danchi_name": "【B】光が丘パークタウン 大通り中央",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4550.html"
    },
    {
        "danchi_name": "【B】光が丘パークタウン いちょう通り八番街",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3910.html"
    },
    {
        "danchi_name": "【C】光が丘パークタウン 大通り南",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3690.html"
    },
    {
        "danchi_name": "【D】グリーンプラザ高松",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4650.html"
    },
    {
        "danchi_name": "【E】(赤塚)アーバンライフゆりの木通り東",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4590.html"
    },
    {
        "danchi_name": "【F】(赤塚古い)むつみ台",
        "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2410.html"
    }
]

# --- メール設定 ---
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = os.environ.get('SMTP_PORT')
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = FROM_EMAIL

# --- 状態管理 ---
def get_current_status():
    """status.json から現在の通知状態を団地ごとに読み込む"""
    initial_status = {d['danchi_name']: 'not_available' for d in MONITORING_TARGETS}
    try:
        with open('status.json', 'r') as f:
            saved_status = json.load(f)
            return {name: saved_status.get(name, 'not_available') for name in initial_status}
    except (FileNotFoundError, json.JSONDecodeError):
        return initial_status

def update_status(new_statuses):
    """status.json を団地ごとの新しい通知状態に更新する"""
    try:
        with open('status.json', 'w') as f:
            json.dump(new_statuses, f, indent=4, ensure_ascii=False)
        print("📄 状態ファイル(status.json)を更新しました。")
    except Exception as e:
        print(f"🚨 エラー: 状態ファイル書き込み失敗: {e}")

# --- メール送信 ---
def send_alert_email(subject, body):
    """空き情報が見つかった場合にメール送信 (STARTTLS方式)"""
    try:
        now_jst = datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')
        msg = MIMEText(f"{body}\n\n(実行時刻: {now_jst})", 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = TO_EMAIL

        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"✅ メール送信済み: {TO_EMAIL} (件名: {subject})")
            return "通知メール送信済み"
    except Exception as e:
        print(f"🚨 メール送信エラー: {e}")
        return "メール送信失敗"

# --- Selenium WebDriver ---
def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# --- 空きチェック ---
def check_vacancy_selenium(danchi, driver):
    danchi_name = danchi["danchi_name"]
    url = danchi["url"]

    print(f"\n--- 団地チェック: {danchi_name} ---")
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 90)

        # ページメインコンテンツのロード確認
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#main-contents")))
        except TimeoutException:
            print("⚠ メインコンテンツロードタイムアウト")

        # 空きなし要素確認
        no_vacancy_selector = "div.list-none"
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, no_vacancy_selector)))
            return f"空きなし: {danchi_name}", False
        except TimeoutException:
            vacancy_indicator_text = "募集戸数"
            if vacancy_indicator_text in driver.page_source:
                return f"空きあり: {danchi_name}", True
            else:
                return f"空きあり: {danchi_name} (不確実)", True
    except Exception as e:
        print(f"🚨 Seleniumエラー: {e}")
        return f"エラー: {danchi_name}", False

# --- メイン ---
if __name__ == "__main__":
    try:
        driver = setup_driver()
    except Exception as e:
        print(f"🚨 WebDriverセットアップ失敗: {e}")
        exit(1)

    print(f"=== UR空き情報監視スクリプト開始 ({len(MONITORING_TARGETS)} 件) ===")
    current_statuses = get_current_status()
    all_new_statuses = current_statuses.copy()
    newly_available_danchis = []
    results = []

    for danchi_info in MONITORING_TARGETS:
        result_text, is_available = check_vacancy_selenium(danchi_info, driver)
        results.append(result_text)
        time.sleep(1)
        danchi_name = danchi_info['danchi_name']

        if is_available:
            all_new_statuses[danchi_name] = 'available'
            if current_statuses.get(danchi_name) == 'not_available':
                newly_available_danchis.append(danchi_info)
        else:
            all_new_statuses[danchi_name] = 'not_available'

    driver.quit()

    print("\n=== チェック完了 ===")
    for res in results:
        print(f"- {res}")

    if newly_available_danchis:
        print(f"🚨 新規空き情報 {len(newly_available_danchis)} 件")
        for danchi in newly_available_danchis:
            subject = f"【UR空き情報】 {danchi['danchi_name']}"
            body = (
                f"以下の団地で空き情報が出た可能性があります！\n\n"
                f"・【団地名】: {danchi['danchi_name']}\n"
                f"  【URL】: {danchi['url']}\n"
            )
            send_alert_email(subject, body)
            time.sleep(5)
        update_status(all_new_statuses)
    else:
        if all_new_statuses != current_statuses:
            update_status(all_new_statuses)
            print("✅ 状態更新完了 (空き情報なし)")
        else:
            print("✅ 状態変化なし。メール送信なし")

    print("\n=== 監視終了 ===")
