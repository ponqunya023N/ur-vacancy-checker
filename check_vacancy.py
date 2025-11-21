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
    {"danchi_name": "【S】光が丘パークタウン プロムナード十番街", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4350.html"},
    {"danchi_name": "【A】光が丘パークタウン 公園南", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3500.html"},
    {"danchi_name": "【A】光が丘パークタウン 四季の香弐番街", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4100.html"},
    {"danchi_name": "【B】光が丘パークタウン 大通り中央", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4550.html"},
    {"danchi_name": "【B】光が丘パークタウン いちょう通り八番街", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3910.html"},
    {"danchi_name": "【C】光が丘パークタウン 大通り南", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3690.html"},
    {"danchi_name": "【D】グリーンプラザ高松", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4650.html"},
    {"danchi_name": "【E】(赤塚)アーバンライフゆりの木通り東", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4590.html"},
    {"danchi_name": "【F】(赤塚古い)むつみ台", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2410.html"}
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
    initial_status = {d['danchi_name']: 'not_available' for d in MONITORING_TARGETS}
    try:
        with open('status.json', 'r') as f:
            saved_status = json.load(f)
            return {name: saved_status.get(name, 'not_available') for name in initial_status}
    except (FileNotFoundError, json.JSONDecodeError):
        return initial_status

def update_status(new_statuses):
    try:
        with open('status.json', 'w') as f:
            json.dump(new_statuses, f, indent=4, ensure_ascii=False)
        print("📄 状態ファイル(status.json)を更新しました。")
    except Exception as e:
        print(f"🚨 エラー: status.json 書き込み失敗: {e}")

def send_alert_email(subject, body):
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
        print(f"✅ メール送信: {TO_EMAIL} （件名: {subject}）")
        return True
    except Exception as e:
        print(f"🚨 メール送信エラー: {e}")
        return False

# --- Chrome WebDriver 設定 ---
def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# --- 空き確認 ---
def check_vacancy(danchi, driver):
    name, url = danchi['danchi_name'], danchi['url']
    print(f"\n--- チェック: {name} ---\nURL: {url}")
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 90)
        # メインコンテンツロード待機
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#main-contents")))
        except TimeoutException:
            print("⚠️ メインコンテンツロードタイムアウト")
        # 空きなし判定
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.list-none")))
            print("❌ 空きなし確認")
            return False
        except TimeoutException:
            # 空きあり判定: 募集戸数テーブル
            if "募集戸数" in driver.page_source:
                print("✅ 空きあり確認")
                return True
            else:
                print("❓ 不確実: 空き情報不明、空きありとして扱う")
                return True
    except Exception as e:
        print(f"🚨 Selenium致命的エラー: {e}")
        return False

# --- メイン ---
if __name__ == "__main__":
    driver = setup_driver()
    statuses = get_current_status()
    new_statuses = statuses.copy()
    newly_available = []

    for d in MONITORING_TARGETS:
        available = check_vacancy(d, driver)
        if available:
            new_statuses[d['danchi_name']] = 'available'
            if statuses[d['danchi_name']] == 'not_available':
                newly_available.append(d)
        else:
            new_statuses[d['danchi_name']] = 'not_available'
        time.sleep(1)

    driver.quit()

    for d in newly_available:
        subject = f"【UR空き情報アラート】🚨 空きが出ました！ {d['danchi_name']}"
        body = f"空き情報の可能性があります。\n\n団地名: {d['danchi_name']}\nURL: {d['url']}"
        send_alert_email(subject, body)

    update_status(new_statuses)
    print("=== 監視完了 ===")
