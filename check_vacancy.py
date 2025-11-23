import json
import smtplib
import os
import logging
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

STATUS_FILE = "status.json"

def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

def send_email(notifications):
    from_email = os.environ["FROM_EMAIL"]
    to_email = os.environ["TO_EMAIL"]
    smtp_server = os.environ["SMTP_SERVER"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_username = os.environ["SMTP_USERNAME"]
    smtp_password = os.environ["SMTP_PASSWORD"]

    body = "\n".join(notifications)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "UR Vacancy Notification"
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)

    logging.info("メール送信完了")

def scrape_properties():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # ここに対象URLを設定
        page.goto("https://www.ur-net.go.jp/chintai/")
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    # DOM解析ロジックは実際のHTML構造に合わせて調整
    # 仮の例: 各物件を抽出
    properties = soup.find_all("div", class_="property")
    for prop in properties:
        name = prop.find("h2").get_text(strip=True)
        status_text = prop.find("span", class_="status").get_text(strip=True)
        if "空室あり" in status_text:
            results[name] = "available"
        else:
            results[name] = "not_available"
    return results

def main():
    prev_status = load_status()
    current_status = scrape_properties()

    notifications = []
    for key, now in current_status.items():
        before = prev_status.get(key, "not_available")  # 未登録は not_available とみなす
        if before == "not_available" and now == "available":
            logging.info(f"通知対象: {key} 前回={before} → 今回={now}")
            notifications.append(f"{key}: {now}")
        else:
            logging.info(f"通知抑制: {key} 前回={before} 今回={now}")

    if notifications:
        send_email(notifications)
    else:
        logging.info("通知なし: 差分なし")

    save_status(current_status)

if __name__ == "__main__":
    main()
