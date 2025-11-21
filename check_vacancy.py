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
from selenium.common.exceptions import TimeoutException, WebDriverException

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
        print(f"🚨 状態ファイル更新エラー: {e}")

# --- メール送信 ---
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
        print(f"✅ メール送信成功: {TO_EMAIL} (件名: {subject})")
    except Exception as e:
        print(f"🚨 メール送信エラー: {e}")

# --- WebDriverセットアップ ---
def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# --- 空きチェック ---
def check_vacancy_selenium(danchi, driver):
    danchi_name = danchi["danchi_name"]
    url = danchi["url"]
    print(f"\n--- 団地チェック開始: {danchi_name} ---")
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 90)
        # メインコンテンツ待機
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#main-contents")))
            print("🌐 メインコンテンツロード完了")
        except TimeoutException:
            print("⏱ タイムアウト: メインコンテンツロード未完了")
        # 空きなし判定
        no_vacancy_selector = "div.list-none"
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, no_vacancy_selector)))
            print(f"✅ 空きなし: {no_vacancy_selector}検出")
            return False
        except TimeoutException:
            vacancy_indicator_text = "募集戸数"
            if vacancy_indicator_text in driver.page_source:
                print("🚨 空きあり検出: 募集戸数テキスト確認")
                return True
            else:
                print("❓ 不確実: 空き判定要素なし、募集戸数なし")
                return True
    except WebDriverException as e:
        print(f"🚨 Seleniumエラー: {danchi_name} / {e}")
        return False
    except Exception as e:
        print(f"🚨 その他エラー: {danchi_name} / {e}")
        return False

# --- メイン ---
if __name__ == "__main__":
    try:
        driver = setup_driver()
    except Exception as e:
        print(f"🚨 WebDriverセットアップ失敗: {e}")
        exit(1)

    print(f"=== UR空き情報監視スクリプト実行開始 ({len(MONITORING_TARGETS)}団地) ===")
    current_statuses = get_current_status()
    all_new_statuses = current_statuses.copy()
    newly_available = []

    for danchi in MONITORING_TARGETS:
        try:
            is_available = check_vacancy_selenium(danchi, driver)
            danchi_name = danchi['danchi_name']
            if is_available:
                if current_statuses.get(danchi_name) == 'not_available':
                    newly_available.append(danchi)
                all_new_statuses[danchi_name] = 'available'
            else:
                all_new_statuses[danchi_name] = 'not_available'
            time.sleep(1)
        except Exception as e:
            print(f"🚨 チェック中に例外発生: {danchi['danchi_name']} / {e}")
            continue

    driver.quit()

    print("\n=== チェック完了 ===")
    for name, status in all_new_statuses.items():
        print(f"- {name}: {status}")

    if newly_available:
        print(f"🚨 新規空き情報 {len(newly_available)}団地検出")
        for danchi in newly_available:
            subject = f"【UR空き情報】{danchi['danchi_name']}"
            body = f"以下の団地で空き情報が出た可能性があります！\n\n・団地名: {danchi['danchi_name']}\n・URL: {danchi['url']}\n"
            send_alert_email(subject, body)
            time.sleep(5)

    update_status(all_new_statuses)
    print("=== 監視終了 ===")
